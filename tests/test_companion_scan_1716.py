"""INBOX 1716: the window scan at the owner's 2560x1504, 192 dpi monitor. A visible Explorer window is a place to
stand, a maximised browser whose frame overhangs the monitor by its border is a place to hang from (never counted
invisible), and a window the system calls hidden says whether its own style or an owner hid it. Fake win32."""

from __future__ import annotations

import os
from collections import Counter

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import perches  # noqa: E402
from tessellate.core.overlay import win32 as k  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402

MON = (0, 0, 2560, 1504)


def scan(window_list: dict) -> tuple[list, Counter]:
    fake = FakeWin32()
    fake.window_list = window_list
    tally: Counter = Counter()
    return k.windows(fake, os.getpid(), None, [MON], tally), tally


def test_a_visible_explorer_window_at_two_x_is_standable() -> None:
    wins, tally = scan({1: {"rect": (400, 244, 2434, 1400), "title": "Docs", "cls": "CabinetWClass"}})
    assert [p.key for p in perches.top_edges(wins, 200)] == [1] and "invisible" not in tally


def test_a_maximised_browser_overhanging_by_its_border_is_hung_from_not_invisible() -> None:
    wins, tally = scan({2: {"rect": (-13, -13, 2573, 1491), "title": "Tab", "cls": "Chrome_WidgetWin_1", "zoomed": True}})
    assert tally["maximised"] == 1 and "invisible" not in tally
    assert wins[0].hang and not wins[0].perch and perches.top_edges(wins, 200) == []


def test_a_window_hidden_by_both_reads_is_invisible_and_a_style_that_says_shown_is_listed() -> None:
    wins, tally = scan({
        3: {"rect": (400, 244, 2434, 1400), "title": "Docs", "visible": False},
        4: {"rect": (400, 244, 2434, 1400), "title": "Docs", "visible": False, "style": k.WS_VISIBLE},
    })
    assert [w.key for w in wins] == [4] and tally["invisible"] == 1


def test_a_foreground_window_counted_hidden_is_named_so() -> None:
    fake = FakeWin32()
    fake.window_list = {5: {"rect": (400, 244, 2434, 1400), "title": "Docs", "visible": False}}
    fake.foreground = 5
    tally: Counter = Counter()
    k.windows(fake, os.getpid(), None, [MON], tally)
    assert tally["invisible, yet foreground"] == 1


def test_a_hidden_window_near_a_release_says_whether_it_is_titled_and_its_style() -> None:
    """A hidden Explorer or Chrome helper has no title; a hidden real window does: the let-go log tells them apart."""
    fake = FakeWin32()
    fake.window_list = {
        6: {"rect": (400, 244, 2434, 1400), "title": "Docs", "visible": False, "cls": "CabinetWClass"},
        7: {"rect": (400, 244, 2434, 1400), "title": "", "visible": False, "cls": "CabinetWClass"},
    }
    seen: list = []
    k.windows(fake, os.getpid(), None, [MON], Counter(), near=(1000, 244, 100), seen=seen)
    whys = sorted(why for _c, _r, why in seen)
    assert len(whys) == 2 and all(x.startswith("invisible (") and ", style " in x for x in whys), whys
    assert any("(titled," in x for x in whys) and any("(no title," in x for x in whys)


def test_the_owners_1110_classes_and_rects_visible_are_standable_hidden_are_not() -> None:
    """The owner's let-go trace (2560x1504, 192 dpi): the same classes and rects, shown, are places to stand (rects
    are left, top, right, bottom; x 245 to 2165 with top 245 is a real 1920-wide window); hidden they are counted
    invisible, as the helper windows Chrome and Explorer keep are; Progman is a tool window."""
    shown = {
        1: {"rect": (245, 245, 2165, 1300), "title": "Chrome", "cls": "Chrome_WidgetWin_0"},
        2: {"rect": (400, 244, 2434, 1400), "title": "Docs", "cls": "CabinetWClass"},
    }
    wins, tally = scan(shown)
    assert sorted(p.key for p in perches.top_edges(wins, 200)) == [1, 2] and "invisible" not in tally
    hidden = {k_: {**v, "visible": False} for k_, v in shown.items()}
    hidden[3] = {"rect": (0, 0, 2560, 1504), "title": "Program Manager", "cls": "Progman", "ex": k.WS_EX_TOOLWINDOW}
    wins, tally = scan(hidden)
    assert tally["invisible"] == 2 and perches.top_edges(wins, 200) == []


def test_two_placements_in_flight_do_not_flip_the_quick_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Placed at the first size, then the measured one; each read-back saw the other's size and set its own again."""
    import ctypes
    import ctypes.wintypes

    from tessellate.core import desk_companion as dc

    state = {"box": (1296, 824, 640, 680)}
    sets: list = []

    class User32:
        def GetWindowRect(self, _h, ref):
            x, y, w, h = state["box"]
            r = ref._obj
            r.left, r.top, r.right, r.bottom = x, y, x + w, y + h
            return 1

        def SetWindowPos(self, _h, _z, x, y, w, h, _f):
            state["box"] = (x, y, w, h)
            sets.append((x, y, w, h))
            return 1

    monkeypatch.setattr(ctypes, "windll", type("W", (), {"user32": User32()})(), raising=False)
    monkeypatch.setattr(dc.jobs, "thread", lambda _n, fn: None)  # read-backs are run by hand below
    monkeypatch.setattr(dc, "_WANTED", {})
    first, second = (1296, 824, 640, 680), (1296, 1312, 640, 192)
    dc._read_back(7, first, 0, again=True)
    dc._read_back(7, second, 0, again=True)
    state["box"] = second  # the later ask landed
    dc._log_placed(7, first, 0, again=True)  # the older read-back must not drag the window back
    assert state["box"] == second and sets == []
    dc._log_placed(7, second, 0, again=True)
    assert sets == []


# --- INBOX 1778 e: Explorer (style 04cf0000) counted invisible, 535 windows scanned ----------------------------


def test_the_style_of_a_hidden_explorer_has_no_visible_bit_and_a_title_bar_so_it_is_counted_apart() -> None:
    """0x04cf0000 is WS_CLIPSIBLINGS plus a caption, sysmenu, frame and min/max boxes: no WS_VISIBLE (0x10000000), so
    IsWindowVisible and the style agree it is hidden. It is counted as a hidden window with a title bar, not lost in
    the hundreds of title-less helpers EnumWindows returns; one whose style says shown (14cf0000) is a place to stand."""
    assert 0x04CF0000 & k.WS_VISIBLE == 0 and 0x04CF0000 & k.WS_CAPTION == k.WS_CAPTION
    wins, tally = scan({
        1: {"rect": (400, 244, 2434, 1400), "title": "Docs", "cls": "CabinetWClass", "visible": False, "style": 0x04CF0000},
        2: {"rect": (400, 244, 2434, 1400), "title": "Docs", "cls": "CabinetWClass", "style": 0x14CF0000, "visible": False},
        3: {"rect": (0, 0, 1, 1), "title": "", "cls": "MSCTFIME UI", "visible": False, "style": 0x80000000},
    })
    assert tally["invisible, with a title bar"] == 1 and tally["invisible"] == 1
    assert [w.key for w in wins] == [2] and [p.key for p in perches.top_edges(wins, 200)] == [2]


def test_a_style_with_the_high_bit_set_is_read_unsigned() -> None:
    """GetWindowLongW returns a signed 32-bit number: a style with bit 31 set (WS_POPUP) comes back negative, and the
    visible bit is still found after the mask."""
    fake = FakeWin32()
    fake.window_list = {8: {"rect": (400, 244, 2434, 1400), "title": "Pop", "visible": False, "style": -0x6FFF0000}}
    assert k._style(fake, 8) == 0x90010000 and k._shown(fake, 8) == (True, 0x90010000)


def test_off_screen_and_tiny_windows_are_counted_and_are_no_place_to_stand() -> None:
    wins, tally = scan({
        1: {"rect": (-32000, -32000, -31000, -31000), "title": "Parked"},
        2: {"rect": (100, 100, 120, 110), "title": "Sliver"},
        3: {"rect": (400, 244, 2434, 1400), "title": "Docs"},
    })
    assert tally["off-screen"] == 1 and tally["too small"] == 1 and tally["perch"] == 1
    assert [p.key for p in perches.top_edges(wins, 200)] == [3]


def test_the_scan_logs_one_fixed_line_of_skips_per_reason(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    from tessellate.core.overlay import runner

    tally = Counter({"invisible": 500, "invisible, with a title bar": 3, "invisible, yet foreground": 1, "cloaked": 19, "minimised": 9,
                     "tool window": 11, "own overlay": 1, "own process": 2, "off-screen": 4, "too small": 5})
    bare = runner.OverlayRunner.__new__(runner.OverlayRunner)
    bare._last_skip_line = ""
    with caplog.at_level(logging.INFO, logger=runner.logger.name):
        bare._log_skips(tally)
        bare._log_skips(tally)  # unchanged: said once
    lines = [m for m in caplog.messages if m.startswith("overlay: window scan skipped")]
    assert lines == ["overlay: window scan skipped: invisible 504 (of those with a title bar 4), cloaked 19, minimised 9, tool window 11, too small 5, own window 3, off-screen 4"]
