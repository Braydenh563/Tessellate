""""Go somewhere else" arrives and the new spot is home (INBOX 1696, owner: "I pressed go somewhere else, it just
stayed as it was and started moving to the left and didnt really have any change in animation or body position or
motion, but then it got halfway across my taskbar and it just poofed back to where it was"). Before: a floater's
menu wander was a glide or a swoop half the time (a drift draws the idle frames, so the stand picture slid across the
taskbar), and home moved only on arrival, so a step aside from the caret or the typing zone on the way (a puff to the
nearest edge) left the old home in place and the next decision took it back there (10 of 40 seeds in a fuzz with a
caret on the way). Now a floater's wander is a seen move (a blink, a cloud, a bubble, a portal or the rare puff) and
the spot is home from the moment it is chosen. Fixed clock throughout."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import travel as tv  # noqa: E402
from tests.test_overlay_ride_1670 import make  # noqa: E402

STEP = 0.033


def standing(look: str, gait: str, seed: int, plain: bool = False):
    e, _s = make(look, gait, seed, plain=plain)
    t = 0.0
    while t < 20.0 or e.state != "stand":
        t += STEP
        e.update(t)
    return e, t


@pytest.mark.parametrize("look", ["feminine", "masculine"])
def test_a_floaters_menu_wander_is_a_seen_move_never_a_glide(look: str) -> None:
    seen = []
    for seed in range(1, 17):
        e, t = standing(look, "float", seed)
        assert e.command("wander", t)
        assert e.state == "warp", (seed, e.state, e.modes[-3:])  # before: seeds 2 and 4 drifted (a glide, a swoop)
        seen.append(e.warp["kind"])
    assert set(seen) <= set(tv.VISIBLE) | {"puff"}
    assert len(set(seen)) >= 3  # still a repertoire, not one move


def test_a_walker_still_walks_or_runs_where_it_is_a_gait() -> None:
    e, t = standing("masculine", "walk", 3, plain=True)
    assert e.command("wander", t)
    assert e.state in ("walk", "crouch")


@pytest.mark.parametrize("gait", ["float", "walk"])
def test_the_spot_is_home_from_the_moment_it_is_chosen(gait: str) -> None:
    for seed in range(1, 11):
        e, t = standing("feminine", gait, seed)
        old = e.home_x
        assert e.command("wander", t)
        assert e.home_x != old and abs(e.home_x - old) > 100, seed
        lo, hi = tv.middle(e.current_monitor().area)
        assert not lo < e.home_x + e.size[0] / 2 < hi  # the spot it will rest at, never the middle third


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_a_step_aside_from_the_caret_on_the_way_does_not_take_it_back(seed: int) -> None:
    """The owner's case: the plain glide (the leg a drift draws), and the text box of the window it passes ends it
    part way in a puff to the nearest edge. It must then go on to the new spot, never back to the old one."""
    e, t = standing("feminine", "float", seed, plain=True)
    start = e.x
    assert e.command("wander", t)
    new = e.home_x
    caret_set = False
    back = False
    for _ in range(int(40 / STEP)):
        t += STEP
        if not caret_set and e.state == "drift" and abs(e.x - start) > 120:
            ahead = e.x + (200 if new > start else -200)
            e.set_caret((int(ahead), int(e.y) + 40, int(ahead) + 4, int(e.y) + 70))  # just ahead, on the way
            caret_set = True
        if caret_set and e.state == "warp" and e.then == "evade":
            e.set_caret(None)  # the box is gone once it has stepped aside (the typing stopped)
        e.update(t)
        back = back or (e.then == "home" and abs(e.goal[0] - start) < 60 if e.goal else False)
    assert caret_set
    assert not back
    assert abs(e.x - new) < 40 and e.home_x == pytest.approx(new, abs=40), (seed, start, new, e.x, e.home_x)
