"""INBOX 1683 (u), the owner on the desktop companion: "the take a nap doesnt stick ... it only ever poofs and it
doesnt portal or walk off screen and back on somewhere else, it needs a lot of expansion". A nap holds until it
is woken (a poke, a drag, a menu command, or its own long nap); a leg picks its travel by distance and mood.
Seeded engine, fixed clock; nothing here runs on real Windows."""
from __future__ import annotations

from collections import Counter

import pytest

from tessellate.core.overlay import travel as tv
from tests.test_overlay_ride_1670 import AREA, make


def _run(e, t: float, secs: float, pointer=None, step: float = 0.05) -> float:
    end = t + secs
    while t < end:
        t += step
        e.update(t, pointer)
    return t


def _centre(e) -> tuple[int, int]:
    return int(e.x + e.size[0] / 2), int(e.y + e.size[1] / 2)


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_a_nap_holds_with_roam_pointer_and_caret(gait: str) -> None:
    e, _ = make("masculine", gait, 4)
    t = 100.0
    e.update(t)
    e.roam = True
    px, py = _centre(e)
    assert e.command("nap", t)
    t = _run(e, t, 12.0, (px, py))  # the menu that asked for it is under the pointer: that is not a poke
    e.set_caret((e.x - 40, e.y - 40, e.x + e.size[0] + 40, e.y + e.size[1] + 40))
    states = set()
    nap_end = e.nap_until
    assert 150.0 <= nap_end - 100.0 <= 312.0
    while t < nap_end - 5.0:
        t = _run(e, t, 5.0, (px, py))
        states.add(e.state)
    assert states == {"sleep"}, states


def test_a_nap_is_still_asleep_after_ten_minutes_when_it_is_not_its_own_long_nap() -> None:
    e, _ = make("masculine", "walk", 8)
    t = 100.0
    e.update(t)
    e.command("nap", t)
    t = _run(e, t, 20.0)
    e.nap_until = t + 700.0  # a long sleeper: roam, trip, ambient and follow timers must not end it in 10 minutes
    e.roam = True
    e.trip_ready = e.climb_ready = 0.0
    _run(e, t, 600.0, step=0.2)
    assert e.state == "sleep"


def test_its_own_long_nap_ends_with_a_stretch() -> None:
    e, _ = make("masculine", "walk", 5)
    t = 100.0
    e.update(t)
    e.command("nap", t)
    seen = set()
    for _ in range(int(330 / 0.25)):
        t = _run(e, t, 0.25)
        seen.add((e.state, e.act))
    assert ("act", "stretch") in seen, seen


@pytest.mark.parametrize("seed", [1, 2, 3, 5, 7, 10, 11])
def test_a_nap_asked_for_right_after_the_first_update_is_taken(seed: int) -> None:
    # review of atlascat-1108: at seed 5 the first update sets off for a spell's spot (state "warp") and the command was dropped
    e, _ = make("masculine", "walk", seed)
    t = 100.0
    e.update(t)
    assert e.command("nap", t)
    seen = set()
    for _ in range(int(60 / 0.25)):
        t = _run(e, t, 0.25)
        seen.add(e.state)
    assert "sleep" in seen, (seed, seen)


@pytest.mark.parametrize("how", ["poke", "wake", "wave"])
def test_a_poke_and_a_command_wake_a_nap(how: str) -> None:
    e, _ = make("masculine", "walk", 6)
    t = 100.0
    e.update(t)
    e.command("nap", t)
    t = _run(e, t, 20.0)
    assert e.state == "sleep"
    px, py = _centre(e)
    if how == "poke":
        e.update(t + 0.05, (px, py), ("down", px, py))
        e.update(t + 0.1, (px, py), ("up", px, py))
    else:
        e.command(how, t + 0.05)
    _run(e, t + 0.1, 0.5)
    assert e.state != "sleep", how
    assert e.nap_until == 0.0


def test_it_settles_out_of_the_middle_before_it_sleeps() -> None:
    e, _ = make("masculine", "walk", 7)
    e.presence = False  # Intent moved (INBOX 1692): the first update would start a spell and its warp, which a nap cannot cut
    t = 100.0
    e.update(t)
    e.x = 900.0  # the middle third of 1920
    e._place_on_floor()
    e.command("nap", t)
    # Intent moved (INBOX 1692): the way out of the middle may now be a seen blink, cloud ride or bubble
    # drift as well as a walk; what is kept is that it ends asleep, out of the middle.
    assert e.state in ("walk", "crouch", "warp")
    _run(e, t, 12.0)
    assert e.state == "sleep"
    assert not tv.in_middle(e.x, AREA, e.size[0])


def _wander_legs(gait: str, legs: int = 200) -> tuple[Counter, list[str]]:
    """One engine wandering `legs` times in a row at 1920 wide; the modes it chose, in order."""
    e, _ = make("masculine", gait, 11)
    e.presence = False  # Intent moved (INBOX 1692): a spell would be under way at the first update; this is about wander legs
    t = 100.0
    e.update(t)
    picked: list[str] = []
    for _ in range(legs):
        e.last_active = t
        n = len(e.modes)
        assert e.command("wander", t)
        for _ in range(4000):
            t += 0.016
            e.update(t)
            if e.state in ("stand", "sit") and not e.pending and e.warp is None and e.then != "edgeexit":
                break
        picked.extend(e.modes[n:])
        t += 1.0
    return Counter(picked), picked


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_wander_legs_use_many_modes_rarely_puff_never_repeat_and_wrap_an_edge(gait: str) -> None:
    mix, order = _wander_legs(gait)
    total = len(order)
    assert len(mix) >= 4, mix  # measured before: walk 90 percent, edge, portal and puff 3 percent each, never a run
    assert mix["puff"] / total < 0.10, mix
    # Intent moved (INBOX 1696, the owner: a floater's "Go somewhere else" slid the stand picture across the taskbar):
    # a floater's menu wander is a seen move only, so the glide to an edge before the wrap is a walker's alone
    if gait == "walk":
        assert mix["edge"] >= 1, mix
    else:
        assert not {"glide", "swoop", "edge"} & set(mix), mix
    assert all(a != b for a, b in zip(order, order[1:])), order
