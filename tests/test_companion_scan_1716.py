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
