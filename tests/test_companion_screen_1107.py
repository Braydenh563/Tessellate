"""Research B7: more screen events than a window opening or closing: a window dragged, one maximised or put
back. Pure bookkeeping over the scan (keys, frames, flags; never a title). Fixed clock, no Win32."""

from __future__ import annotations

import random

from tessellate.core.overlay import extras
from tessellate.core.overlay.engine import Engine, Monitor
from tessellate.core.overlay.screenwatch import ScreenWatch
from tessellate.core.overlay.win32 import WinInfo


def win(key: int, rect=(100, 100, 700, 600), hang: bool = False) -> WinInfo:
    return WinInfo(key, rect, not hang, hang)


def test_the_first_scan_is_only_remembered() -> None:
    w = ScreenWatch()
    assert w.states_seen([win(1)]) == []


def test_a_window_moved_over_two_scans_is_a_drag_once_and_a_resize_is_not() -> None:
    w = ScreenWatch()
    w.states_seen([win(1)])
    assert w.states_seen([win(1, (160, 100, 760, 600))]) == []  # one step is not yet a drag
    assert w.states_seen([win(1, (260, 120, 860, 620))]) == ["window_dragged"]
    assert w.states_seen([win(1, (360, 120, 960, 620))]) == []  # said once per drag
    w.states_seen([win(1, (360, 120, 960, 620))])
    assert w.states_seen([win(1, (360, 120, 1200, 900))]) == []  # a resize changes the size: not a drag


def test_a_window_maximised_and_put_back_are_events() -> None:
    w = ScreenWatch()
    w.states_seen([win(1)])
    assert w.states_seen([win(1, (0, 0, 1920, 1040), hang=True)]) == ["window_maximised"]
    assert w.states_seen([win(1, (0, 0, 1920, 1040), hang=True)]) == []
    assert w.states_seen([win(1)]) == ["window_restored"]


def test_each_new_event_has_a_reaction_with_a_visible_act() -> None:
    from tessellate.core.overlay import behaviour as bh

    extras.register()
    for kind in ("window_dragged", "window_maximised", "window_restored"):
        r = extras.REACTIONS[kind]
        assert r.act in bh.ACTIVITIES and bh.AMPLITUDE[r.act] >= 0.05, kind
    e = Engine((100, 120), [Monitor((0, 0, 1920, 1040), 96)], rng=random.Random(2), idle_frames=0, home=(800, 920))
    e.update(0.1)
    assert e.react("window_maximised", 5.0) is True and e.state == "act"
