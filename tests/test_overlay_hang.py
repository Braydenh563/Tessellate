"""A hang takes hold of an edge (INBOX 1660, the owner: "it thinks its hanging but its just
rocking a little left to right and hanging in mid air"). `hang.png`'s drawn rows start 57 px
below the frame's top, so the frame is lifted by that measured margin and the hands touch
the top of the work area or the bottom edge of a window's title bar under them."""

from __future__ import annotations

import random

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor, Perch
from tessellate.core.overlay.sprites import SpriteSet

SIZE = (100, 120)
SHARE = 0.195
LIFT = SHARE * SIZE[1]
ONE = [Monitor((0, 0, 1920, 1040), 96)]
WIN = Perch(11, 500, 300, 1100)


def make(seed=2, **kw) -> Engine:
    kw.setdefault("gait", "float")
    e = Engine(SIZE, ONE, rng=random.Random(seed), home=(800, 920), hang_top=SHARE, **kw)
    e.climb_ready = float("inf")
    e.plain_legs = True  # the trip to the edge is the plain drift here; the vanishes have their own file (INBOX 1670)
    return e


def run_to(e: Engine, state: str, t: float = 1.0, limit: float = 60.0) -> float:
    end = t + limit
    while e.state != state and t < end:
        t += 0.016
        e.update(t)
    return t


def hands(e: Engine) -> float:
    """The y of the hands: the frame's top plus the measured clear rows."""
    return e.y + SHARE * SIZE[1]


def test_the_shipped_hang_frames_have_a_measured_top_margin() -> None:
    from PIL import Image

    for look in ("masculine", "feminine"):
        s = SpriteSet(look)
        with Image.open(s.directory / "hang.png") as im:
            box = im.convert("RGBA").getchannel("A").point(lambda a: 255 if a >= 8 else 0).getbbox()
        assert box and 40 <= box[1] <= 80  # the owner's 57 px at the shipped scale
        assert s.top_share("hang") == pytest.approx(box[1] / im.size[1])
        assert 0.1 < s.top_share("hang") < 0.3


def test_a_floater_hangs_with_its_hands_on_the_top_of_the_work_area() -> None:
    e = make()
    e._perform("hang", 1.0)
    run_to(e, "hang")
    assert e.state == "hang" and e.hang_on is None
    assert hands(e) == pytest.approx(0.0) and e.y == pytest.approx(-LIFT)


def test_a_walker_rises_so_the_hands_meet_the_top_too() -> None:
    e = make(gait="walk")
    e._perform("hang", 1.0)
    run_to(e, "hang")
    assert e.state == "hang" and hands(e) == pytest.approx(0.0)


def test_a_thrown_floater_that_reaches_the_ceiling_hangs_by_the_hands() -> None:
    e = make()
    # Intent kept, the throw made hard: the ceiling holds a hard upward throw only (INBOX 1670, 15:45Z: "nearly every
    # time I throw it no matter how hard, it goes to the top"), so this one is launched hard: at 0.96 of
    # `CEIL_LEAVE` (intent moved, INBOX 1719 a: it was 2,600 px/s, now past the line where a throw leaves the top).
    e.x, e.y, e.vx, e.vy = 800.0, 40.0, 0.0, -0.96 * eng.CEIL_LEAVE
    e._start_fly(0.0, -0.96 * eng.CEIL_LEAVE)
    run_to(e, "hang", 1.0, 5.0)
    assert e.state == "hang" and hands(e) == pytest.approx(0.0)


def hang_on_window(seed_limit=60):
    for seed in range(seed_limit):
        e = make(seed)
        e.set_windows([WIN], 0.5)
        e._perform("hang", 1.0)
        if e.hang_on is not None:
            return e
    raise AssertionError("no seed chose the window")


def test_a_hang_can_take_hold_of_the_bottom_edge_of_a_windows_title_bar() -> None:
    e = hang_on_window()
    run_to(e, "hang")
    assert e.state == "hang" and e.hang_on == WIN
    assert hands(e) == pytest.approx(WIN.top + eng.TITLE_BAR)
    centre = e.x + SIZE[0] / 2
    assert WIN.left + eng.HANG_HANDS * SIZE[0] <= centre <= WIN.right - eng.HANG_HANDS * SIZE[0]


def test_the_title_bar_is_scaled_with_the_monitor() -> None:
    two = [Monitor((0, 0, 3840, 2080), 192)]
    win = Perch(5, 1000, 600, 2200)
    for seed in range(60):
        e = Engine((200, 240), two, rng=random.Random(seed), home=(1600, 1800), gait="float", hang_top=SHARE)
        e.big_ready = e.climb_ready = float("inf")
        e.set_windows([win], 0.5)
        e._perform("hang", 1.0)
        if e.hang_on is not None:
            run_to(e, "hang")
            assert e.y + SHARE * 240 == pytest.approx(600 + eng.TITLE_BAR * 2)
            return
    raise AssertionError("no seed chose the window")


def test_it_lets_go_when_the_window_it_holds_goes_or_moves_away_from_under_the_hands() -> None:
    e = hang_on_window()
    run_to(e, "hang")
    e.set_windows([], 20.0)
    assert e.state != "hang" and e.hang_on is None
    e = hang_on_window()
    run_to(e, "hang")
    e.set_windows([WIN._replace(top=WIN.top + 80)], 20.0)
    assert e.state != "hang"
    e = hang_on_window()
    run_to(e, "hang")
    e.set_windows([WIN._replace(left=1500, right=1900)], 20.0)  # out from under the hands
    assert e.state != "hang"


def test_it_keeps_hanging_when_the_window_stays_and_follows_a_tiny_move() -> None:
    e = hang_on_window()
    run_to(e, "hang")
    e.set_windows([WIN._replace(top=WIN.top + 2)], 20.0)
    assert e.state == "hang" and e.hang_on is not None


def test_a_window_that_goes_while_it_floats_over_ends_the_trip_without_a_hang() -> None:
    e = hang_on_window()
    # A long trip starts with a short crouch (INBOX 1670: a transition, not a snap).
    assert e.state in ("crouch", "drift") and e.then == "hang"
    e.set_windows([], 1.2)
    assert e.state == "stand" and e.hang_on is None
    run_to(e, "hang", 1.3, 3.0)
    assert e.state != "hang"


def test_it_never_hangs_where_no_edge_is_under_the_hands() -> None:
    """Over many hangs, with windows coming and going, the hands are always on the top of
    the work area or on a window's title bar that is there."""
    rng = random.Random(9)
    hung = 0
    for seed in range(40):
        e = make(seed)
        t = 1.0
        for n in range(6):
            wins = [] if rng.random() < 0.4 else [Perch(1, rng.randrange(0, 900), rng.randrange(60, 700), 1000 + rng.randrange(0, 900))]
            e.set_windows(wins, t)
            e._enter("stand", t)
            e.big_ready = 0.0
            e._perform("hang", t)
            while e.state in ("crouch", "drift", "stand") and t < 1000:
                t += 0.016
                e.update(t)
                if e.state == "stand":
                    break
            if e.state == "hang":
                hung += 1
                on_top = hands(e) == pytest.approx(0.0)
                on_bar = any(hands(e) == pytest.approx(w.top + eng.TITLE_BAR) and w.left < e.x + 50 < w.right for w in wins)
                assert on_top or on_bar, (seed, n, hands(e), wins)
            e._let_go()
            t += 8
            e.update(t)
    assert hung > 100


def test_a_hang_holds_still_x_never_changes_while_hanging() -> None:
    """INBOX 1663: "slides a little from side to side while hanging"."""
    for seed in range(1, 6):
        e = make(seed)
        e._perform("hang", 1.0)
        t, xs, ys = 1.0, set(), set()
        for _ in range(1500):
            t += 0.033
            o = e.update(t)
            if e.state == "hang":
                xs.add(o.x)
                ys.add(o.y)
        assert len(xs) == 1 and len(ys) == 1, (seed, xs, ys)


@pytest.mark.parametrize("gait", ["float", "walk"])
def test_a_click_on_a_hanger_opens_the_menu_and_it_keeps_hanging(gait: str) -> None:
    """INBOX 1690 c: "if the desktop companion is hanging and i click it to show a
    popup menu, it stops visibly hanging and just floats there"."""
    e = make(gait=gait)
    e._perform("hang", 1.0)
    t = run_to(e, "hang")
    x, y = e.x, e.y
    cx, cy = int(e.x + 40), int(e.y + 60)
    down = e.update(t + 0.02, event=("down", cx, cy))
    assert down.frame == "hang"  # the press itself keeps the hang pose
    out = e.update(t + 0.06, event=("up", cx, cy))
    assert out.click == "left"
    for i in range(200):  # the menu stays open about three seconds
        out = e.update(t + 0.1 + i * 0.016)
        assert e.state == "hang" and out.frame == "hang"
    assert (e.x, e.y) == pytest.approx((x, y)) and hands(e) == pytest.approx(0.0)
