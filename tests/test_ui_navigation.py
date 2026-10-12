from kivy.uix.screenmanager import Screen

import main
from main import BackGestureScreenManager


class FakeTouch:
    def __init__(self, uid, x, y):
        self.uid = uid
        self.x = x
        self.y = y
        self.grabbed_by = None

    @property
    def pos(self):
        return self.x, self.y

    def grab(self, widget):
        self.grabbed_by = widget

    def ungrab(self, widget):
        assert self.grabbed_by is widget
        self.grabbed_by = None

    def push(self):
        pass

    def pop(self):
        pass

    def apply_transform_2d(self, *_args):
        pass


class FakeApp:
    def __init__(self):
        self.back_count = 0

    def navigate_back(self):
        self.back_count += 1
        return True


def manager_on(screen_name):
    app = FakeApp()
    manager = BackGestureScreenManager(app_instance=app)
    manager.size = (320, 640)
    manager.add_widget(Screen(name=screen_name))
    manager.current = screen_name
    return manager, app


def swipe(manager, touch, end_x, end_y):
    assert manager.on_touch_down(touch)
    touch.x, touch.y = end_x, end_y
    assert manager.on_touch_move(touch)
    assert manager.on_touch_up(touch)


def test_ios_back_swipe_uses_left_edge_only(monkeypatch):
    monkeypatch.setattr(main, "platform", "ios")
    manager, app = manager_on("settings")
    swipe(manager, FakeTouch(1, 4, 300), 100, 305)
    assert app.back_count == 1

    manager, app = manager_on("settings")
    touch = FakeTouch(2, 316, 300)
    assert not manager.on_touch_down(touch)
    assert app.back_count == 0


def test_android_back_swipes_inward_from_both_sides(monkeypatch):
    monkeypatch.setattr(main, "platform", "android")
    for start_x, end_x in ((4, 100), (316, 220)):
        manager, app = manager_on("settings")
        swipe(manager, FakeTouch(start_x, start_x, 300), end_x, 305)
        assert app.back_count == 1


def test_short_or_diagonal_edge_gestures_do_not_navigate():
    manager, app = manager_on("settings")
    swipe(manager, FakeTouch(1, 4, 300), 42, 301)
    assert app.back_count == 0

    manager, app = manager_on("settings")
    swipe(manager, FakeTouch(2, 4, 300), 110, 380)
    assert app.back_count == 0


def test_gameplay_and_main_menu_keep_edge_touches(monkeypatch):
    monkeypatch.setattr(main, "platform", "android")
    for screen_name in ("menu", "game"):
        manager, app = manager_on(screen_name)
        touch = FakeTouch(3, 4, 300)
        assert not manager.on_touch_down(touch)
        assert manager._back_touch is None
        assert app.back_count == 0
