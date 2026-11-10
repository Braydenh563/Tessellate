"""Research T7: the window filter agrees with Alt-Tab. A store app's ApplicationFrameWindow with cloak 0 is a
window; a cloaked (suspended) one is not; a popup that is not its owner's last active one is no window of its own
(it still hides what is under it). Fake win32, no real windows."""

from __future__ import annotations

import os
from collections import Counter

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import perches  # noqa: E402
from tessellate.core.overlay import win32 as k  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402

MON = (0, 0, 1920, 1080)


def listed(window_list: dict) -> tuple[list, Counter]:
    fake = FakeWin32()
    fake.window_list = window_list
    tally: Counter = Counter()
    return k.windows(fake, os.getpid(), None, [MON], tally), tally


def test_a_store_app_frame_with_cloak_zero_is_a_perch_and_a_cloaked_one_is_not_listed() -> None:
    wins, _t = listed({1: {"rect": (100, 200, 900, 700), "title": "Calculator", "cls": "ApplicationFrameWindow"}})
    assert [p.key for p in perches.top_edges(wins, 200)] == [1]
    wins, tally = listed({1: {"rect": (100, 200, 900, 700), "title": "Calculator", "cloaked": 1}})
    assert wins == [] and tally["cloaked"] == 1


def test_an_owner_with_a_dialog_open_is_no_perch_but_still_hides_what_is_under_it() -> None:
    wins, tally = listed({
        2: {"rect": (300, 300, 600, 500), "title": "Save as", "root": 3},  # the dialog, on top
        3: {"rect": (100, 200, 900, 700), "title": "Editor", "popup": 2},  # its owner: the dialog is its last popup
    })
    assert [w.key for w in wins] == [2, 3]
    assert tally["owned popup"] == 1 and [p.key for p in perches.top_edges(wins, 200)] == [2]


def test_an_ordinary_window_is_its_own_last_active_popup() -> None:
    wins, tally = listed({1: {"rect": (100, 200, 900, 700), "title": "Editor"}})
    assert [p.key for p in perches.top_edges(wins, 200)] == [1] and "owned popup" not in tally
