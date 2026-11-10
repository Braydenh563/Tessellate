"""INBOX 1721 (the owner, real Windows 11, 2560x1600, a maximised browser): (a) a pat while hanging got no reaction and a
typing burst went unanswered in state hang; (b) the hands were about 30 px below the top of a maximised window (the
title-bar offset on a bar that is the screen's top); (c) a figure with no standable top warped in place. Fixed clock,
seeded rng, FakeWin32; real Windows is unverified."""

from __future__ import annotations

import os
import random

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import extras, perches
from tessellate.core.overlay import win32 as k
from tessellate.core.overlay.engine import Engine, Monitor
from tests._overlay_fake import FakeWin32

SHARE = 0.195
MON = (0, 0, 2560, 1560)


def maximised_bar(frame_known: bool) -> eng.Perch:
    """The hang spot a maximised browser gives on Windows 11: GetWindowRect has the invisible 8 px border (top -8), the
    visible top is 0. `frame_known` False is DWM answering nothing, so the border must be clipped away."""
    fake = FakeWin32()
    win = {"rect": MON, "outer": (-8, -8, 2568, 1568), "title": "Chrome", "zoomed": True}
    if not frame_known:
        win["frame"] = (0, 0, 0, 0)  # an empty frame: the rectangle from GetWindowRect is used
    fake.window_list = {1: win}
    wins = k.windows(fake, os.getpid(), None, [MON])
    got = perches.hang_spots(wins, 120)
    assert len(got) == 1 and got[0].kind == "bar"
    return got[0]


@pytest.mark.parametrize("frame_known", [True, False])
@pytest.mark.parametrize("dpi", [96, 144])
def test_the_hands_meet_the_visible_top_of_a_maximised_window(frame_known: bool, dpi: int) -> None:
    bar = maximised_bar(frame_known)
    assert bar.top == 0  # the -8 resize border is not the edge
    size = (round(100 * dpi / 96), round(120 * dpi / 96))
    for seed in range(40):
        e = Engine(size, [Monitor(MON, dpi)], rng=random.Random(seed), home=(800, 1400), hang_top=SHARE, gait="float")
        e.big_ready = e.climb_ready = float("inf")
        e.set_windows([], 0.5, hangs=[bar])
        e._perform("hang", 1.0)
        if e.hang_on is not None:
            t = 1.0
            while e.state != "hang" and t < 60:
                t += 0.016
                e.update(t)
            assert e.state == "hang" and e.hang_on.kind == "bar"
            assert e.y + SHARE * size[1] == pytest.approx(0.0)  # hands on the visible edge, not 32 * scale below it
            return
    raise AssertionError("no seed chose the bar")


def hanger(seed: int = 3) -> Engine:
    e = Engine((100, 120), [Monitor((0, 0, 1920, 1040), 96)], rng=random.Random(seed), home=(800, 920), hang_top=SHARE, gait="float")
    e.big_ready = e.climb_ready = float("inf")
    e._perform("hang", 1.0)
    t = 1.0
    while e.state != "hang" and t < 60:
        t += 0.016
        e.update(t)
    assert e.state == "hang"
    e.ex.cool.clear()
    return e


def test_a_click_on_a_hanger_is_answered_with_a_swing_and_a_face_and_keeps_the_grip() -> None:
    e = hanger()
    t = e.now + 1.0
    px, py = int(e.x + 50), int(e.y + 60)
    e.update(t, (px, py), ("down", px, py))
    e.update(t + 0.05, (px, py), ("up", px, py))
    assert e.state == "hang" and e.ex.over is not None and e.ex.over[0] == "joy"
    swing = [abs(e._target_pose(e.hang_kick_at + d).drag) for d in (0.2, 0.6, 1.0)]
    quiet = [abs(e._target_pose(e.hang_kick_at + eng.HANG_KICK_FOR + 1 + d).drag) for d in (0.2, 0.6, 1.0)]
    assert e.hang_kick_at > 0 and max(swing) > max(quiet)  # the kick shows in the hem


@pytest.mark.parametrize("kind", ["typing_burst", "window_opened", "app_switched", "pat", "poke_giggle"])
def test_a_hanger_answers_a_screen_event_or_a_touch_on_the_edge(kind: str) -> None:
    e = hanger()
    assert e.react(kind, e.now + 5.0) is True
    assert e.state == "hang"  # the answer is hang-safe: a face and a swing, never an act that drops the grip
    assert e.ex.over is not None and e.ex.over[0] == extras.REACTIONS[kind].face


def test_a_hang_that_is_changing_leaves_an_event_to_the_runners_queue() -> None:
    e = hanger()
    e.releasing = True
    assert e.react("typing_burst", e.now + 5.0) is False
    e.releasing, e.swing_to = False, eng.Perch(5, 0, 900, 400)
    assert e.react("typing_burst", e.now + 5.0) is False


def test_a_hanger_stays_quiet_for_someone_typing() -> None:
    e = hanger()
    e.quiet = True
    assert e.react("window_opened", e.now + 5.0) is False


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("then", ["home", "spell", "settle"])
def test_a_vanish_never_takes_it_to_a_spot_beside_itself(gait: str, then: str) -> None:
    """INBOX 1721 c: in the taskbar corner it "periodically vanish[ed] and reappear[ed] in the exact same spot": a leg of a
    few px was given a blink, a cloud or a portal. A warp needs `WARP_MIN` (0.3) figure widths of distance."""
    from tests.test_overlay_ride_1670 import make

    for seed in range(60):
        e, _s = make("masculine", gait, seed)
        e.x = 1700.0
        e._place_on_floor()
        e.now = 5.0
        e._go((e.x + 0.2 * e.size[0], e.y), then, 5.0)  # about 35 px, past the 12 px that is no move at all
        assert e.state != "warp", (seed, e.warp)
    far = None
    for seed in range(60):  # and a far leg still may
        e, _s = make("masculine", gait, seed)
        e.x = 1700.0
        e._place_on_floor()
        e._go((100.0, e.y), "spell", 5.0)
        far = far or e.state == "warp"
    assert far
