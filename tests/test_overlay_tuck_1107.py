"""INBOX 1683 k, ledger N5: tuck behind a smaller window with an open side. It walks to the window's edge, the clip
is exactly the overlap, it peeks round the edge, and it comes out when that window moves, closes, minimises, is
covered, or is the one being typed in. Fake clock, no Win32; real Windows is unverified."""

from __future__ import annotations

import random

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import perches, sprites
from tessellate.core.overlay.engine import Cover, Engine, Monitor
from tessellate.core.overlay.win32 import WinInfo

SIZE = (100, 120)
FULL = (0, 0, 1920, 1080)
FLOOR = 1080 - SIZE[1]
#: a window snapped to the right half, reaching the floor: its open side is the left
RIGHT_HALF = (1000, 100, 1920, 1080)
#: and to the left half: the open side is the right
LEFT_HALF = (0, 100, 900, 1080)
MIDDLE = (600, 100, 1300, 1080)


def make(**kw) -> Engine:
    kw.setdefault("hang_top", 0.2)
    e = Engine(SIZE, [Monitor(FULL, 96, FULL, ())], home=(400, 700), rng=random.Random(5), idle_frames=0, now=0.0, **kw)
    e.update(0.1)
    return e


def see(e: Engine, *covers: Cover, now: float | None = None) -> None:
    e.set_windows([], e.now if now is None else now, (), covers)


def tucked(e: Engine, rect, edge: str | None = None, key: int = 7, at: float = 2.0, above=()) -> eng.Output:
    """Show the window to the engine, tuck behind it, run until it has been peeking `at` seconds."""
    see(e, Cover(key, rect, above))
    t = e.now
    spots = [s for s in e._tuck_spots(e.current_monitor()) if edge in (None, s.edge)]
    assert spots, "no place to tuck"
    e._peek(t, "tuck")
    out = e.update(t)
    while t < 90.0 and not (e.state == "peek" and e.tuck is not None and t - e.peek_started >= at):
        t += 0.033
        out = e.update(t)
    assert e.state == "peek" and e.tuck is not None, (e.state, e.tuck)
    return out


def opaque(w: int, h: int) -> sprites.Frame:
    return sprites.Frame(w, h, bytes([200, 100, 50, 255]) * (w * h), 0, 0, (0, 0, w, h))


def run_to(e: Engine, state: str, limit: float = 30.0) -> None:
    t = e.now
    while e.state != state and t < e.now + limit:
        t += 0.033
        e.update(t)
    assert e.state == state


# --- where it can tuck ---------------------------------------------------------------------------------------------

def test_a_window_with_an_open_side_that_reaches_the_floor_is_a_place_to_tuck() -> None:
    e = make()
    see(e, Cover(7, RIGHT_HALF))
    (spot,) = e._tuck_spots(e.current_monitor())
    assert (spot.edge, spot.x, spot.y) == ("right", 1000 - SIZE[0], FLOOR)  # its left side is open: it stands outside it
    see(e, Cover(7, LEFT_HALF))
    (spot,) = e._tuck_spots(e.current_monitor())
    assert (spot.edge, spot.x) == ("left", 900)


def test_a_window_open_on_both_sides_offers_both() -> None:
    e = make()
    see(e, Cover(7, MIDDLE))
    assert {s.edge for s in e._tuck_spots(e.current_monitor())} == {"left", "right"}


@pytest.mark.parametrize(
    "rect, why",
    [
        ((0, 100, 1920, 1080), "no open side"),
        ((50, 100, 1900, 1080), "the sides are narrower than the figure"),
        ((600, 100, 1300, 700), "it does not reach the floor, so the feet would show"),
        ((600, 1000, 1300, 1080), "its top is below the head"),
        ((600, 100, 650, 1080), "narrower than the figure it hides"),
    ],
)
def test_a_window_without_room_or_reach_is_no_place(rect, why) -> None:
    e = make()
    see(e, Cover(7, rect))
    assert e._tuck_spots(e.current_monitor()) == [], why


def test_a_window_covered_where_it_would_hide_is_no_place() -> None:
    e = make()
    see(e, Cover(7, RIGHT_HALF, ((800, 0, 1100, 1080),)))
    assert e._tuck_spots(e.current_monitor()) == []
    see(e, Cover(7, RIGHT_HALF, ((1500, 0, 1900, 1080),)))  # a window over the far end of it hides nothing at the edge
    assert len(e._tuck_spots(e.current_monitor())) == 1


def test_the_window_being_typed_in_is_never_tucked_behind() -> None:
    e = make()
    see(e, Cover(7, RIGHT_HALF))
    e.set_caret((1300, 500, 1302, 520))
    assert e._tuck_spots(e.current_monitor()) == []
    e.set_caret((200, 500, 202, 520))  # typing in some other window
    assert len(e._tuck_spots(e.current_monitor())) == 1


def test_the_scan_must_be_recent_and_motion_on_and_windows_on() -> None:
    e = make()
    see(e, Cover(7, RIGHT_HALF), now=0.1)
    e.now = 0.1 + eng.TUCK_FRESH + 0.5
    assert e._tuck_spots(e.current_monitor()) == []
    e.now = 1.0
    assert len(e._tuck_spots(e.current_monitor())) == 1
    e.roam_windows = False
    assert e._tuck_spots(e.current_monitor()) == []


def test_a_window_adds_the_tuck_to_the_peek_choice_and_the_mood_bends_it() -> None:
    e = make()
    assert "tuck" not in dict(e._peek_edges(e.current_monitor(), 1.0))
    see(e, Cover(7, RIGHT_HALF), now=0.9)
    plain = dict(e._peek_edges(e.current_monitor(), 1.0))
    assert plain["tuck"] == eng.PEEK_TUCK
    e.mind.feel("startled", 1.0)
    assert dict(e._peek_edges(e.current_monitor(), 1.5))["tuck"] == eng.PEEK_TUCK * 2


def test_the_seeded_choice_reaches_the_tuck_in_the_share_its_weight_gives() -> None:
    e = make()
    see(e, Cover(7, RIGHT_HALF), now=0.9)
    seen = []
    e._go = lambda goal, then, now, plain=False: seen.append(then)  # type: ignore[method-assign]
    e._rise = lambda to, then, now, drawn_from=None: seen.append(then)  # type: ignore[method-assign]
    for i in range(600):
        e.rng = random.Random(i)
        e.tuck_goal = None
        e._peek(1.0)
    weights = dict(e._peek_edges(e.current_monitor(), 1.0))
    share = sum(1 for s in seen if s.startswith("tuck_")) / 600
    assert share == pytest.approx(weights["tuck"] / sum(weights.values()), abs=0.06) and share > 0.1


# --- the tuck itself -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rect, edge", [(RIGHT_HALF, "right"), (LEFT_HALF, "left")])
def test_the_clip_equals_the_overlap_with_the_window(rect, edge) -> None:
    e = make()
    out = tucked(e, rect, edge)
    w, h = SIZE
    left, top, right, bottom = out.clip
    assert e.peek_edge == edge and (top, bottom) == (0, h)
    if edge == "right":  # the window is on the right of the figure: what shows ends where the window begins
        assert (left, out.x + right) == (0, rect[0]) and out.y == FLOOR
    else:
        assert (right, out.x + left) == (w, rect[2])
    rows = sprites.clipped(opaque(w, h), out.clip)
    shown = sum(1 for i in range(w * h) if rows.bgra[i * 4 + 3])
    assert 0 < shown < w * h and shown == (right - left) * h


@pytest.mark.parametrize("rect, edge", [(RIGHT_HALF, "right"), (LEFT_HALF, "left")])
def test_it_peeks_round_the_edge_and_hides_all_of_itself_behind_the_window(rect, edge) -> None:
    e = make()
    tucked(e, rect, edge)
    t, sinks = e.now, []
    while e.state == "peek" and t < 90:
        t += 0.033
        out = e.update(t)
        sinks.append(e.sink)
        if e.sink >= 0.999:  # all behind it: nothing of the figure is outside the window
            wall = rect[0] if edge == "right" else rect[2]
            assert (out.x + out.clip[2] <= wall) if edge == "right" else (out.x + out.clip[0] >= wall)
    assert max(sinks) > 0.99 and e.state == "stand" and e.tuck is None and e.sink == 0.0


def test_a_click_on_the_visible_part_lands_and_brings_it_out() -> None:
    e = make()
    out = tucked(e, RIGHT_HALF)
    px, py = out.x + (out.clip[0] + out.clip[2]) // 2, out.y + SIZE[1] // 2
    assert out.clip[2] > out.clip[0] and px < RIGHT_HALF[0]
    t = e.now + 0.05
    e.update(t, (px, py), ("down", px, py))
    e.update(t + 0.05, (px, py), ("up", px, py))
    assert e.state in ("emerge", "wave")


def test_a_window_that_moved_ends_the_tuck_in_the_scan_that_sees_it() -> None:
    e = make()
    tucked(e, RIGHT_HALF)
    see(e, Cover(7, (1000, 100, 1920, 1080)))  # the same: nothing happens
    assert e.state == "peek"
    see(e, Cover(7, (1200, 100, 1920, 1080)))
    assert e.state == "emerge"
    run_to(e, "wave")
    assert e.tuck is None and e.peek_edge is None and e.sink == 0.0


def test_a_window_a_few_pixels_off_is_not_moved() -> None:
    e = make()
    tucked(e, RIGHT_HALF)
    see(e, Cover(7, (1000 + eng.PERCH_MOVED, 100, 1920, 1080)))
    assert e.state == "peek"


@pytest.mark.parametrize("scan", ["closed", "minimised"])
def test_a_window_that_is_gone_ends_the_tuck_in_the_scan_that_misses_it(scan: str) -> None:
    e = make()
    tucked(e, RIGHT_HALF)
    see(e)  # a closed or minimised window is not in the list
    assert e.state == "emerge" and any("tuck" in n for n in e.notes)
    run_to(e, "wave")
    assert e.tuck is None


def test_another_window_covering_the_edge_ends_the_tuck() -> None:
    e = make()
    tucked(e, RIGHT_HALF)
    see(e, Cover(7, RIGHT_HALF, ((700, 0, 1100, 1080),)))
    assert e.state == "emerge"


def test_a_window_covering_only_its_far_end_does_not() -> None:
    e = make()
    tucked(e, RIGHT_HALF)
    see(e, Cover(7, RIGHT_HALF, ((1500, 0, 1900, 1080),)))
    assert e.state == "peek"


def test_typing_in_the_window_it_is_behind_brings_it_out() -> None:
    e = make()
    tucked(e, RIGHT_HALF)
    e.set_caret((200, 500, 202, 520))
    see(e, Cover(7, RIGHT_HALF))
    assert e.state == "peek"  # typing elsewhere: it stays
    e.set_caret((1300, 500, 1302, 520))
    assert e.state == "emerge"


def test_a_tuck_that_loses_its_window_on_the_way_does_not_begin() -> None:
    e = make()
    see(e, Cover(7, RIGHT_HALF))
    e._peek(e.now, "tuck")
    assert e.then.startswith("tuck_") or e.state == "walk" or e.pending is not None
    see(e)  # it is gone before the figure gets there
    t = e.now
    while e.state in ("walk", "crouch", "leap", "drift", "warp", "stand") and t < 60 and e.tuck is None:
        t += 0.033
        e.update(t)
        if e.state == "stand" and t > e.now + 0.5:
            break
    assert e.tuck is None and e.state != "peek"


def test_a_resume_while_tucked_stands_it_up() -> None:
    e = make()
    tucked(e, RIGHT_HALF)
    e.resume(e.now + 100)
    assert e.state == "stand" and e.tuck is None and e.sink == 0.0


def test_a_tuck_holds_longer_than_a_peek_so_the_window_can_be_seen_to_matter() -> None:
    e = make()
    tucked(e, RIGHT_HALF)
    assert e.state_until - e.peek_started == eng.TUCK_PLAN[-1][0] > eng.PEEK_PLAN[-1][0]


# --- the scan: what the runner hands the engine ---------------------------------------------------------------------

def win(key: int, rect, perch: bool = True, solid: bool = True) -> WinInfo:
    return WinInfo(key, rect, perch, False, solid)


def test_the_windows_worth_tucking_behind_carry_the_ones_above_that_overlap_them() -> None:
    wins = [win(3, (800, 50, 1200, 400), perch=False), win(2, (1000, 100, 1920, 1080)), win(1, (0, 0, 400, 300)), win(4, (100, 0, 200, 50))]
    by = {c.key: c for c in perches.tuck_spots(wins, 100)}
    assert set(by) == {1, 2}  # a tool window is no place; a window 50 high is too small
    assert by[2].above == ((800, 50, 1200, 400),) and by[1].above == ()


def test_a_tool_overlay_hides_no_window_and_a_window_too_small_is_not_a_place() -> None:
    wins = [win(1, FULL, perch=False, solid=False), win(2, (1000, 100, 1920, 1080)), win(3, (10, 10, 60, 60))]
    got = perches.tuck_spots(wins, 100)
    assert [(c.key, c.above) for c in got] == [(2, ())]



# --- the runner: a real scan on the fake win32 --------------------------------------------------------------------

def _runner_tucked():
    from tests.test_overlay_roam_runner import started, tick

    r, fake, clock, _ = started()
    fake.window_list = {5: {"rect": (1000, 100, 1920, 1040), "title": "Notes"}}
    clock.t = r.engine.trip_ready + 5
    r.engine.last_active = clock.t
    tick(r, clock, 0.1, 15)  # one scan or two: the window is known
    assert [c.key for c in r.engine.covers] == [5]
    return r, fake, clock, tick


def test_the_runner_hands_the_engine_the_windows_to_tuck_behind() -> None:
    pytest.importorskip("PIL")
    r, fake, clock, _tick = _runner_tucked()
    assert r.engine.covers[0].rect == (1000, 100, 1920, 1040) and r.engine.covers[0].above == ()
    r.stop()


@pytest.mark.parametrize("change", ["closes", "minimises", "moves"])
def test_a_scan_a_quarter_second_later_brings_it_out(change: str) -> None:
    pytest.importorskip("PIL")
    r, fake, clock, tick = _runner_tucked()
    e = r.engine
    spot = next(s for s in e._tuck_spots(e.current_monitor()) if s.cover.key == 5)
    e.x, e.y = spot.x, spot.y
    e.tuck_goal = 5
    e._arrive_tuck(spot.edge, clock.t)
    assert e.state == "peek" and e.tuck is not None and r._wants_scan(clock.t)
    if change == "closes":
        del fake.window_list[5]
    elif change == "minimises":
        fake.window_list[5]["iconic"] = True
    else:
        fake.window_list[5]["rect"] = (1300, 100, 1920, 1040)
    tick(r, clock, 0.1, 4)  # SCAN_RIDING is 0.25 s
    assert e.state != "peek" and e.tuck is None
    r.stop()
