"""INBOX 1683 (g): the desktop companion perches on windows (the owner on Windows had never seen it), logs what the
window list returns, rides a moved window and hops off a closed one. Fixed clock, seeded randomness, the runner's
fakes; real Windows is unverified."""
from __future__ import annotations

import logging
import os
from collections import Counter

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import win32 as k
from tessellate.core.overlay.engine import Perch
from tests.test_overlay_moves import make
from tests.test_overlay_roam_runner import due, started, tick

# --- (g) it perches on windows ------------------------------------------------------------------


def test_the_climb_act_is_in_the_table_and_only_when_a_window_is_worth_it() -> None:
    assert "climb" in eng.ACTS  # it was missing, so `_can_climb` had no call site and only a rare trip ever climbed
    e = make(seed=3)
    e.climb_ready = 0.0
    assert "climb" not in dict(e._act_table(100.0, 0.0))
    e.set_windows([Perch(11, 400, 700, 1200)], 0.0)
    assert "climb" in dict(e._act_table(100.0, 0.0))
    e.climb_ready = 500.0
    assert "climb" not in dict(e._act_table(100.0, 0.0))


def test_with_windows_about_it_perches_every_few_minutes() -> None:
    perched = []
    for gait in ("walk", "float"):
        e = make(seed=4, gait=gait)
        e.plain_legs = False
        e.roam_windows = True
        wins = [Perch(11, 400, 700, 1200), Perch(12, 1300, 600, 1800)]
        e.set_windows(wins, 0.0)
        e.climb_ready = 30.0
        t, n, prev, out = 0.0, 0, None, e.update(0.0)
        while t < 3600:
            t += min(1.0, (out.wake_ms or 1000) / 1000.0)
            out = e.update(t, event=("move", 0, 0)) if int(t) % 20 == 0 else e.update(t)
            if e.perch is not None and prev is None:
                n += 1
            prev = e.perch
            e.set_windows(wins, t)
        perched.append(n)
    assert all(n >= 2 for n in perched), perched  # measured 3 an hour on average over ten seeds; was 1.0 (a climb came only with a rare trip)


def test_the_windows_are_scanned_before_a_climb_is_due() -> None:
    r, fake, clock, _ = started()
    fake.window_list = {5: {"rect": (300, 400, 1100, 900), "title": "Notes"}}
    r.engine.trip_ready = clock.t + 5000.0
    r.engine.climb_ready = clock.t + 0.5
    r.engine.last_active = clock.t
    n = fake.names("user32").count("EnumWindows")
    tick(r, clock, 0.1, 15)
    assert fake.names("user32").count("EnumWindows") > n
    r.stop()


def test_the_window_list_is_logged_as_counts_and_reasons_never_titles(caplog: pytest.LogCaptureFixture) -> None:
    r, fake, clock, _ = started()
    fake.window_list = {
        2: {"rect": (200, 300, 900, 800), "title": "Secret tool", "ex": k.WS_EX_TOOLWINDOW},
        4: {"rect": (200, 300, 900, 800), "title": "Secret max", "zoomed": True},
        5: {"rect": (200, 300, 900, 800), "title": "Secret min", "iconic": True},
        6: {"rect": (200, 300, 900, 800), "title": "Secret away", "cloaked": True},
        8: {"rect": (200, 300, 900, 800), "title": "Secret hidden", "visible": False},
        10: {"rect": (1000, 500, 1700, 900), "title": "Secret good"},
    }
    due(r, clock)
    with caplog.at_level(logging.INFO, logger="tessellate.core.overlay.runner"):
        tick(r, clock, 0.1, 15)
    lines = [m for m in caplog.messages if m.startswith("overlay: windows listed")]
    assert lines, caplog.messages
    line = lines[0]
    assert "windows listed 3" in line and "standable top edges 1" in line
    for why in ("1 tool window", "1 maximised", "1 minimised", "1 cloaked", "1 invisible", "1 perch"):
        assert why in line, line
    assert "Secret" not in " ".join(caplog.messages)
    assert len(lines) == len(set(lines)), lines  # logged when it changes, not every second
    r.stop()


def test_a_shell_cloaked_window_is_not_listed_whatever_the_cloak_value() -> None:
    from tests._overlay_fake import FakeWin32

    fake = FakeWin32()
    # DWM_CLOAKED_APP 1, DWM_CLOAKED_SHELL 2 (a window on another virtual desktop), DWM_CLOAKED_INHERITED 4.
    fake.window_list = {n: {"rect": (100, 100, 900, 700), "title": "w", "cloaked": n} for n in (1, 2, 4)}
    fake.window_list[9] = {"rect": (100, 100, 900, 700), "title": "w"}
    tally: Counter = Counter()
    wins = k.windows(fake, os.getpid(), None, [(0, 0, 1920, 1040)], tally=tally)
    assert [w.key for w in wins] == [9] and tally["cloaked"] == 3


def test_the_frame_is_the_visible_bounds_not_the_window_rect_with_its_invisible_border() -> None:
    from tests._overlay_fake import FakeWin32

    fake = FakeWin32()
    # Windows 10 and 11 give a top-level window a 7 px invisible resize border: the figure stands on the drawn edge.
    fake.window_list = {3: {"rect": (107, 100, 893, 700), "title": "w", "outer": (100, 93, 900, 707)}}
    assert k.windows(fake, os.getpid(), None, [(0, 0, 1920, 1040)])[0].rect == (107, 100, 893, 700)


def test_a_window_dragged_sideways_carries_a_figure_standing_on_it() -> None:
    for gait in ("walk", "float"):
        e = make(seed=3, gait=gait)
        win = Perch(11, 400, 700, 1200)
        e.climb_ready = 0.0
        e.set_windows([win], 1.0)
        e._perform("climb", 1.0)
        t = 1.0
        while e.perch is None and t < 60:
            t += 0.016
            e.update(t)
        assert e.perch is not None
        x0 = e.x
        e.set_windows([Perch(11, 700, 700, 1500)], t)
        assert e.perch is not None and e.x == pytest.approx(x0 + 300), gait


def test_a_closed_window_sends_a_walker_hopping_off_and_a_floater_drifting() -> None:
    hops = 0
    for seed in range(20):
        e = make(seed=seed)
        e.climb_ready = 0.0
        e.set_windows([Perch(11, 400, 700, 1200)], 1.0)
        e._perform("climb", 1.0)
        t = 1.0
        while e.perch is None and t < 60:
            t += 0.016
            e.update(t)
        e.set_windows([], t)
        assert e.perch is None and e.state == "fall"
        hops += e.vx != 0.0
    assert hops >= 8, hops  # a push away from the window, not always a plain step off
