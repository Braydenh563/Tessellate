"""INBOX 1689: a press outside the open desk panel closes it even when the panel never had focus."""

from tessellate.core import desk_companion as dc


class FakeUser32:
    def __init__(self, down=False, cursor=(0, 0), rect=(100, 100, 300, 400)):
        self.down, self.cursor, self.rect = down, cursor, rect

    def GetAsyncKeyState(self, vk):  # noqa: N802 - the Win32 name
        return 0x8000 if self.down and vk == dc.VK_LBUTTON else 0

    def GetCursorPos(self, ref):  # noqa: N802
        ref._obj.x, ref._obj.y = self.cursor
        return 1

    def GetWindowRect(self, handle, ref):  # noqa: N802
        r = ref._obj
        r.left, r.top, r.right, r.bottom = self.rect
        return 1


def test_a_fresh_press_outside_the_panel_closes_it():
    u = FakeUser32(down=True, cursor=(10, 10))
    assert dc.press_outside(u, 1, was_down=False) == (True, True)


def test_a_press_inside_the_panel_keeps_it_open():
    u = FakeUser32(down=True, cursor=(150, 200))
    assert dc.press_outside(u, 1, was_down=False) == (False, True)


def test_the_held_click_that_opened_the_panel_does_not_close_it():
    u = FakeUser32(down=True, cursor=(10, 10))
    assert dc.press_outside(u, 1, was_down=True) == (False, True)


def test_no_press_is_no_close():
    assert dc.press_outside(FakeUser32(), 1, was_down=True) == (False, False)


def test_the_watch_closes_the_panel_on_a_press_outside(monkeypatch):
    calls = []

    class Host:
        panel_shown, closing, _away_watch = True, False, object()

        def panel_blur(self):
            calls.append("blur")
            self.panel_shown = False
            return True

    u = FakeUser32(cursor=(10, 10))
    reads = iter([False, True])
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)
    monkeypatch.setattr(dc, "mouse_down", lambda user32: next(reads, True))
    host = Host()
    dc.DeskCompanion._click_away_loop(host, u, 1)
    assert calls == ["blur"] and host._away_watch is None
