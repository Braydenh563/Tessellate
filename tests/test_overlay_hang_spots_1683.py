"""INBOX 1683 (w): the desk companion on a real desktop (maximised windows, the taskbar, a floating window) has more
than the taskbar to go to. The window filter keeps a maximised window as a hang spot, `perches.hang_spots` turns the
list into title bars and bottom edges, and the log counts them. Fixed clock, seeded randomness, fakes; real Windows
is unverified."""
from __future__ import annotations

import logging
import os
from collections import Counter

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import perches
from tessellate.core.overlay import win32 as k
from tests._overlay_fake import FakeWin32
from tests.test_overlay_roam_runner import due, started, tick

MON = [(0, 0, 1920, 1040)]


def test_a_maximised_window_is_kept_as_a_hang_spot_not_a_perch() -> None:
    fake = FakeWin32()
    fake.window_list = {
        1: {"rect": (0, 0, 1920, 1040), "title": "Max", "zoomed": True},
        2: {"rect": (200, 300, 900, 800), "title": "Tool max", "zoomed": True, "ex": k.WS_EX_TOOLWINDOW},
        3: {"rect": (200, 300, 900, 800), "title": "Min", "iconic": True, "zoomed": True},
        4: {"rect": (200, 300, 900, 800), "title": "Hidden", "visible": False, "zoomed": True},
        5: {"rect": (200, 300, 900, 800), "title": "Away", "cloaked": True, "zoomed": True},
        6: {"rect": (1000, 500, 1700, 900), "title": "Floating"},
    }
    wins = {w.key: w for w in k.windows(fake, os.getpid(), None, MON)}
    assert set(wins) == {1, 2, 6}  # invisible, cloaked and minimised stay out
    assert (wins[1].perch, wins[1].hang) == (False, True)
    assert wins[2].hang is False  # a tool window is never a place to hang
    assert (wins[6].perch, wins[6].hang) == (True, False)


def test_hang_spots_are_a_maximised_title_bar_and_a_floating_windows_bottom_edge() -> None:
    wins = [k.WinInfo(2, (500, 300, 1300, 700), True), k.WinInfo(1, (0, 0, 1920, 1040), False, True)]  # topmost first
    got = {p.key: p for p in perches.hang_spots(wins, 120)}
    assert got[1] == eng.Perch(1, 0, 0, 1920, "bar")
    assert got[-2] == eng.Perch(-2, 500, 700, 1300, "bottom")
    assert len(got) == 2


def test_a_window_above_covers_part_of_a_bottom_edge_and_a_narrow_rest_is_dropped() -> None:
    wins = [k.WinInfo(1, (500, 600, 700, 900), True), k.WinInfo(2, (300, 300, 1300, 700), True)]
    assert {p.key: p for p in perches.hang_spots(wins, 120)}[-2] == eng.Perch(-2, 700, 700, 1300, "bottom")
    narrow = [k.WinInfo(1, (400, 600, 720, 900), True), k.WinInfo(2, (300, 300, 800, 700), True)]
    assert -2 not in {p.key for p in perches.hang_spots(narrow, 120)}  # only 100 wide is left


def test_the_log_line_counts_hang_spots(caplog: pytest.LogCaptureFixture) -> None:
    r, fake, clock, _ = started()
    fake.window_list = {
        10: {"rect": (1000, 500, 1700, 900), "title": "Secret good"},
        4: {"rect": (0, 0, 1920, 1040), "title": "Secret max", "zoomed": True},
    }
    due(r, clock)
    with caplog.at_level(logging.INFO, logger="tessellate.core.overlay.runner"):
        tick(r, clock, 0.1, 15)
    line = next(m for m in caplog.messages if m.startswith("overlay: windows listed"))
    assert "hang spots 3" in line, line  # the maximised title bar, the floating window's title bar and its bottom edge
    assert "1 maximised" in line and "Secret" not in line
    assert r.engine.hangs and Counter(p.kind for p in r.engine.hangs) == {"bar": 1, "bottom": 1}
    r.stop()
