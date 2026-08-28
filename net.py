# Networking for Swellfire 2-player games.
#
# One device hosts a game and another joins it using the host's IP address. The
# host runs the real game and is in charge of it. The joining device sends its
# steering input and shots to the host and draws whatever the host sends back.
# Each message is JSON with a 4-byte length in front, so both sides know where
# one message ends and the next begins.
#
# This uses only the Python standard library (socket, threading, json, struct,
# queue), so the Android and iOS builds need no extra packages.
#
# Threads here never touch the game widgets. They only read and write sockets
# and put decoded messages on an inbox Queue. The game drains that inbox on its
# normal loop, on the main thread, which is the same approach autoplay.py uses.

import json
import socket
import struct
import threading
import queue
import urllib.request

try:
    import ssl
except ImportError:  # a Python build without the _ssl module
    ssl = None

DEFAULT_PORT = 50007
PROTOCOL_VERSION = 1
CONNECT_TIMEOUT = 6.0           # seconds to wait when joining a host
MAX_FRAME = 1024 * 1024         # drop a peer that announces a frame bigger than this
_HEADER = struct.Struct(">I")   # 4-byte big-endian length prefix


def pack_message(obj):
    """Return one bounded, length-prefixed JSON object frame."""
    if not isinstance(obj, dict):
        raise TypeError("network messages must be JSON objects")
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    if not data or len(data) > MAX_FRAME:
        raise ValueError("network message exceeds frame limit")
    return _HEADER.pack(len(data)) + data



def get_local_ip():
    # Find this device's address on the local network so the host can show it.
    # Connecting a UDP socket sends nothing; it just picks the network card that
    # would be used to reach the internet and reports its address. Falls back to
    # the loopback address if there is no network.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        probe.close()
    return ip


# Services that report back the caller's internet-facing IP address. Used only
# to help set up internet play (the host needs to share this address).
PUBLIC_IP_SERVICES = ("https://api.ipify.org", "https://ifconfig.me/ip",
                      "https://icanhazip.com")


def _ssl_contexts():
    # Verified SSL contexts to try for the HTTPS lookups.
    #
    # Desktop Python finds the system CA bundle, so the default verified context
    # works. The Python shipped inside the iOS / Android builds has no CA bundle,
    # so mobile packages include certifi and use its CA store. Never fall back to
    # an unverified request: a failed lookup is safer and the host screen already
    # explains how to find and share the address manually.
    if ssl is None:
        return []
    contexts = []
    try:
        import certifi
        contexts.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass
    try:
        contexts.append(ssl.create_default_context())
    except Exception:
        pass
    return contexts


def get_public_ip(timeout=4.0):
    # Ask a public service for this device's internet-facing IPv4 address.
    # The request is made only when the Host screen opens and always uses
    # certificate verification. Response size is capped before decoding.
    contexts = _ssl_contexts()
    request_headers = {"User-Agent": "Swellfire/1.0"}
    for url in PUBLIC_IP_SERVICES:
        request = urllib.request.Request(url, headers=request_headers)
        for ctx in contexts:
            try:
                with urllib.request.urlopen(
                    request, timeout=timeout, context=ctx
                ) as response:
                    raw = response.read(65)
                if len(raw) > 64:
                    continue
                text = raw.decode("ascii").strip()
            except Exception:
                continue
            parts = text.split(".")
            if len(parts) == 4 and all(
                part.isdigit() and 0 <= int(part) <= 255 for part in parts
            ):
                return text
    return None




def local_subnet_prefix():
    # The first three parts of this device's local IP, with a trailing dot, for
    # example "192.168.1.". It is a handy starting point on the Join screen,
    # because the host is usually on the same network, so the joiner only types
    # the last number. Returns "" when there is no useful local address.
    ip = get_local_ip()
    parts = ip.split(".")
    if len(parts) == 4 and parts[0] != "127":
        return ".".join(parts[:3]) + "."
    return ""


def _recv_loop(sock, inbox, on_closed):
    # Read framed JSON objects from sock and put each decoded one on inbox.
    # Runs on its own thread and calls on_closed when the link ends.
    buffer = bytearray()
    need = None
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)
            while True:
                if need is None:
                    if len(buffer) < _HEADER.size:
                        break
                    need = _HEADER.unpack(bytes(buffer[:_HEADER.size]))[0]
                    del buffer[:_HEADER.size]
                    if need == 0 or need > MAX_FRAME:
                        raise ValueError("invalid frame size")
                if len(buffer) < need:
                    break
                payload = bytes(buffer[:need])
                del buffer[:need]
                need = None
                try:
                    decoded = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    # Skip one malformed message without killing a healthy link.
                    continue
                if isinstance(decoded, dict):
                    inbox.put(decoded)
    except Exception:
        pass
    finally:
        on_closed()



class _Link:
    # Shared send and close behavior for one TCP connection.
    def __init__(self):
        self.inbox = queue.Queue()
        self.sock = None
        self._send_lock = threading.Lock()
        self._closed = False

    def _start_reader(self):
        threading.Thread(target=_recv_loop,
                         args=(self.sock, self.inbox, self._on_closed),
                         daemon=True).start()

    def _on_closed(self):
        # Release the descriptor and report an unexpected disconnect once.
        sock = self.sock
        self.sock = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        if not self._closed:
            self._closed = True
            self.inbox.put({"t": "_disconnected"})


    def send(self, obj):
        sock = self.sock
        if sock is None or self._closed:
            return
        try:
            with self._send_lock:
                sock.sendall(pack_message(obj))
        except Exception:
            self._on_closed()

    def send_leave(self):
        # Either side can tell the other it is leaving the game.
        self.send({"t": "leave"})

    def stop(self):
        # Safe to call more than once.
        self._closed = True
        sock = self.sock
        self.sock = None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass


class NetHost(_Link):
    # Waits for one joining player, then exchanges messages with them.
    def __init__(self, port=DEFAULT_PORT):
        super().__init__()
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        self.port = port
        self.connected = False
        self._server = None
        self._accept_thread = None

    def start_listening(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.port))
            server.listen(1)
        except Exception:
            server.close()
            self._server = None
            raise
        self._server = server
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def _accept_loop(self):
        server = self._server
        if server is None:
            return
        try:
            client, _addr = server.accept()
        except Exception:
            return
        finally:
            try:
                server.close()
            except Exception:
                pass
            self._server = None
        if self._closed:
            try:
                client.close()
            except Exception:
                pass
            return
        self.sock = client
        self.connected = True
        self._start_reader()
        self.inbox.put({"t": "_connected"})

    def send_state(self, snapshot):
        self.send(snapshot)

    def send_event(self, kind, name="", data=None):
        self.send({"t": "event", "kind": kind, "name": name, "data": data or {}})

    def send_start(self, mode, level, seed):
        self.send({"t": "start", "version": PROTOCOL_VERSION,
                   "mode": mode, "level": level, "seed": seed})

    def stop(self):
        # Safe to call more than once.
        self._closed = True
        server = self._server
        if server is not None:
            # The accept thread may be blocked waiting for a player. Closing the
            # socket from another thread does not free the port while accept is
            # blocked, so we connect to ourselves to wake it. It then sees we are
            # closing and returns, which releases the port.
            try:
                waker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                waker.settimeout(0.5)
                waker.connect(("127.0.0.1", self.port))
                waker.close()
            except Exception:
                pass
            try:
                server.close()
            except Exception:
                pass
            self._server = None
        thread = self._accept_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        super().stop()


class NetClient(_Link):
    # Joins a host at the given IP and exchanges messages with it.
    def connect(self, ip, port=DEFAULT_PORT):
        # The connect itself can block, so do it on a thread and report the
        # result through inbox. The UI stays responsive either way.
        host = ip.strip() if isinstance(ip, str) else ""
        try:
            port = int(port)
        except (TypeError, ValueError):
            port = 0
        if not host or len(host) > 253 or not 1 <= port <= 65535:
            self.inbox.put({"t": "_connect_failed", "why": "invalid address"})
            return
        threading.Thread(target=self._connect, args=(host, port), daemon=True).start()

    def _connect(self, ip, port):
        try:
            sock = socket.create_connection((ip, port), timeout=CONNECT_TIMEOUT)
            sock.settimeout(None)
        except Exception as error:
            self.inbox.put({"t": "_connect_failed", "why": str(error)})
            return
        if self._closed:
            try:
                sock.close()
            except Exception:
                pass
            return
        self.sock = sock
        self._start_reader()
        self.send({"t": "hello", "version": PROTOCOL_VERSION})
        self.inbox.put({"t": "_connected"})

    def send_input(self, tx, ty, fire=False):
        # `tx` is the player's lateral position in [0,1] play-area units; `ty`
        # is unused for the autoscroll runner but kept in the schema so the
        # host can extend it later (e.g. brakes / jump). `fire` triggers a
        # one-shot manual fire if the autoplay GA is off on the client.
        self.send({"t": "input", "tx": round(tx, 4), "ty": round(ty, 4),
                   "fire": bool(fire)})
