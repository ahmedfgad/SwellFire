"""Regression tests for bounded, object-only multiplayer frames."""

import json
import queue
import socket

import net


def test_pack_message_accepts_only_bounded_objects(monkeypatch):
    try:
        net.pack_message(["not", "an", "object"])
    except TypeError:
        pass
    else:
        raise AssertionError("non-object network payload was accepted")

    monkeypatch.setattr(net, "MAX_FRAME", 8)
    try:
        net.pack_message({"message": "too large"})
    except ValueError:
        pass
    else:
        raise AssertionError("oversized network payload was accepted")


def test_receive_loop_skips_non_object_json():
    sender, receiver = socket.socketpair()
    inbox = queue.Queue()
    closed = []
    list_payload = json.dumps([1, 2, 3]).encode("utf-8")
    sender.sendall(net._HEADER.pack(len(list_payload)) + list_payload)
    sender.sendall(net.pack_message({"t": "hello"}))
    sender.close()

    net._recv_loop(receiver, inbox, lambda: closed.append(True))
    receiver.close()
    assert inbox.get_nowait() == {"t": "hello"}
    assert inbox.empty()
    assert closed == [True]


def test_invalid_client_address_fails_without_starting_thread():
    client = net.NetClient()
    client.connect("", 0)
    assert client.inbox.get_nowait()["t"] == "_connect_failed"


def test_host_releases_socket_when_bind_fails(monkeypatch):
    class FailingSocket:
        def __init__(self):
            self.closed = False

        def setsockopt(self, *_args):
            pass

        def bind(self, *_args):
            raise OSError("busy")

        def close(self):
            self.closed = True

    failing = FailingSocket()
    monkeypatch.setattr(net.socket, "socket", lambda *_args: failing)
    host = net.NetHost()
    try:
        host.start_listening()
    except OSError:
        pass
    else:
        raise AssertionError("bind failure was swallowed")
    assert failing.closed is True
    assert host._server is None
