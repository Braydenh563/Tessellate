"""INBOX 1696 (i), the owner on the desktop companion (Windows, 2560x1504 at 200%, about 8 frames a second): "I pressed
go somewhere else, it just stayed as it was and started moving to the left [...] but then it got halfway across my
taskbar and it just poofed back to where it was". The slow crawl was PACE_GAP (`test_overlay_slow_tick_1108.py`); these
are the ways a trip in flight could be sent back where it came from in one step:

- a text caret near the taskbar line (a terminal's last line): the figure stepped aside to the NEAREST screen edge,
  which halfway across is the edge it set off from (reproduced: 3 of 5 seeds went back, x 1345 to 2263);
- a runner restart mid-trip (frames drawn, a look or motion answer, "Let it walk"): the new engine forgot the trip and
  the home chosen from the menu, so its middle-third relocation took it to the nearer edge, the old one;
- a runner that died: the next start read the place saved at the last drop, not where it was;
- the saved place was written only on a drop, never when a trip arrived.

Seeded engine, fake win32 runner, fake runner factory, fixed clocks. Real Windows is not run here."""
from __future__ import annotations

import math
import random

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay.engine import Engine, Monitor  # noqa: E402
from tessellate.core.overlay.sprites import IDLE_COUNT, SpriteSet  # noqa: E402

#: The owner's screen in physical px: 2560 wide, 1504 high less a 40 px (80 physical) taskbar, at 200%.
AREA = (0, 0, 2560, 1424)
OWNER = [Monitor(AREA, 192)]
TICK = 0.125  # 8 frames a second


def _engine(seed: int, gait: str = "walk", look: str = "masculine", home: tuple[int, int] | None = None, now: float = 0.0,
            plain: bool = True) -> Engine:
    s = SpriteSet(look)
    size = s.size(192)
    e = Engine(size, OWNER, rng=random.Random(seed), gait=gait, hang_top=s.top_share("hang"), idle_frames=IDLE_COUNT,
               home=home or (AREA[2] - size[0] - 200, AREA[3] - size[1]), now=now)
    e.set_metrics(s.metrics(192))
    e.climb_ready = e.big_ready = math.inf
    e.plain_legs = plain
    e.roam = True
    return e


def _wander(e: Engine) -> tuple[float, float, float]:
    t = 0.0
    while t < 15.0 or e.state != "stand":
        t += TICK
        e.update(t)
    old = e.x
    assert e.command("wander", t)
    return t, old, e.home_x


def _halfway(e: Engine, t: float, old: float, goal: float) -> float:
    while abs(e.x - old) <= abs(goal - old) / 2:
        t += TICK
        e.update(t)
        assert e.goal is not None or e.state == "crouch", "never got halfway"
    assert e.state == "walk"
    return t


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_a_caret_halfway_never_sends_the_trip_back_where_it_came_from(seed: int) -> None:
    e = _engine(seed)
    t, old, goal = _wander(e)
    t = _halfway(e, t, old, goal)
    here = e.x
    cx, cy = int(e.x + e.size[0] / 2), int(e.y + e.size[1] / 2)
    e.set_caret((cx - 10, cy, cx + 10, cy + 30))  # a caret right over it: it has to step aside
    t += TICK
    e.update(t)
    assert e.state == "warp" and e.warp["kind"] in ("blink", "portal", "puff"), e.state  # a seen move, not a slide
    dst = e.warp["dst"][0]
    assert abs(dst - goal) < abs(here - goal), (old, here, dst, goal)  # on, toward where it was going, never back
    e.set_caret(None)
    end = t + 30.0
    while t < end:
        t += TICK
        e.update(t)
    assert abs(e.x - goal) < 60 * e._scale() and abs(e.x - old) > 400, (e.x, goal, old)  # the trip was finished


@pytest.mark.parametrize("gait,look", [("walk", "masculine"), ("float", "feminine")])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_restart_mid_trip_keeps_the_place_and_finishes_the_trip(seed: int, gait: str, look: str) -> None:
    e = _engine(seed, gait, look)
    t, old, goal = _wander(e)
    while abs(e.x - old) <= abs(goal - old) / 2:
        t += TICK
        e.update(t)
    carried = e.carry()
    fresh = _engine(seed + 10, gait, look, home=(int(e.x), int(e.y)), now=t)
    here = fresh.x
    assert abs(here - e.x) < 2
    fresh.take(carried, t)
    nearest_old, end = abs(here - old), t + 200.0  # past RELOCATE_AFTER: the middle-third rule must not undo it
    while t < end:
        t += TICK
        fresh.update(t)
        nearest_old = min(nearest_old, abs(fresh.x - old))
    assert abs(fresh.x - goal) < 60 * fresh._scale(), (fresh.x, goal)
    assert nearest_old >= abs(here - old) - 60 * fresh._scale(), (nearest_old, here, old)  # never back toward the old spot


def test_a_restart_on_a_trip_of_its_own_ends_it_in_place_and_keeps_the_home() -> None:
    e = _engine(3)
    t = 0.0
    while t < 15.0 or e.state != "stand":
        t += TICK
        e.update(t)
    home = e.home_x
    e._go((AREA[2] / 2 - 300, e.ground_y()), "rest", t)  # a stroll of its own, not the menu's
    t += 3.0
    e.update(t)
    carried = e.carry()
    assert carried["goal"] is None and carried["home_x"] == home
    fresh = _engine(4, home=(int(e.x), int(e.y)), now=t)
    fresh.take(carried, t)
    assert fresh.home_x == home and fresh.state == "stand" and abs(fresh.x - e.x) < 2


def test_a_menu_trip_arriving_counts_as_a_new_place_and_a_stroll_does_not() -> None:
    e = _engine(2)
    t, old, goal = _wander(e)
    before, t0 = e.home_arrivals, t
    while e.home_arrivals == before:
        t += TICK
        e.update(t)
        assert t - t0 < 60
    assert e.home_arrivals == before + 1 and abs(e.x - goal) < 2
    e._go((e.x + 300 * (1 if e.x < AREA[2] / 2 else -1), e.ground_y()), "rest", t)
    while e.goal is not None or e.state in ("walk", "warp"):
        t += TICK
        e.update(t)
    assert e.home_arrivals == before + 1  # a stroll away from home is not where it lives


# --- the coordinator: a restart, a death and an arrival (fake runner factory) -------------------------------------

from types import SimpleNamespace  # noqa: E402

from tessellate.core import desk_companion as dc  # noqa: E402
from tests.test_desk_companion import prefs  # noqa: E402,F401
from tests.test_desk_overlay_wiring import FakeRunner, _says, over  # noqa: E402,F401


class Carrying(FakeRunner):
    """With the real runner's two hooks the coordinator sets (`OverlayRunner.on_place`, `OverlayRunner.carried`)."""

    on_place = None
    carried = None


@pytest.fixture()
def carrying(over):  # noqa: F811
    over._overlay_factory = lambda **kw: Carrying(ok=over.box.ok, **kw)  # noqa: SLF001
    return over


TRIP = {"home_x": 300.0, "homed_for": 4.0, "goal": 300.0, "then": "settle"}


def test_a_restart_mid_trip_hands_the_trip_to_the_new_runner(carrying, prefs):  # noqa: F811
    prefs[dc.OVERLAY_POS_PREF] = [2071, 1120]  # the last drop: the old spot
    carrying.main_window.evaluate_js = _says(mode="fades", reason="setting")
    carrying.set_main_hidden(True)
    first = FakeRunner.started[0]
    first.engine = SimpleNamespace(x=1290, y=1120, carry=lambda: dict(TRIP))
    carrying.main_window.evaluate_js = _says(mode="full")
    carrying.set_main_hidden(False)
    carrying.set_main_hidden(True)
    second = FakeRunner.started[1]
    assert second.home == (1290, 1120) and second.carried == TRIP


def test_a_runner_that_died_mid_trip_comes_back_where_it_stood_not_at_the_last_drop(carrying, prefs):  # noqa: F811
    prefs[dc.OVERLAY_POS_PREF] = [2071, 1120]
    carrying.set_main_hidden(True)
    first = FakeRunner.started[0]
    first.engine = SimpleNamespace(x=1290, y=1120, carry=lambda: dict(TRIP))
    first.on_died()
    assert carrying.runner is None and carrying.overlay_failed
    carrying.set_main_hidden(False)  # the app in front: the figure is tried again at the next minimise
    carrying.set_main_hidden(True)
    again = FakeRunner.started[-1]
    assert again is not first and again.home == (1290, 1120) and again.carried == TRIP


def test_the_runner_takes_up_a_carried_trip_and_reports_its_arrival() -> None:
    """The real runner on the fake win32 (1920x1040 at 96): a restart's carry goes on to its goal, and the arrival is
    handed to `on_place` once."""
    import time

    from tests.test_overlay_runner import _pump, make

    r, fake, clock, *_ = make(home=(1500, 920))
    places: list[tuple[int, int]] = []
    r.on_place = lambda x, y: places.append((x, y))
    r.carried = {"home_x": 300.0, "homed_for": 4.0, "goal": 300.0, "then": "settle"}
    assert r.start()
    try:
        assert r.engine.home_x == 300.0 and (r.engine.goal or r.engine.pending or r.engine.warp or r.engine.edge_plan)
        r.show()
        _pump(r, fake, clock, 40.0, until=lambda: bool(places))
        time.sleep(0.05)
        assert len(places) == 1 and abs(places[0][0] - 300) < 40, places
    finally:
        r.stop()


def test_a_trip_that_arrives_saves_the_place_without_moving_the_panel(carrying, prefs):  # noqa: F811
    prefs[dc.OVERLAY_POS_PREF] = [2071, 1120]
    carrying.set_main_hidden(True)
    runner = FakeRunner.started[0]
    assert callable(runner.on_place)
    corner = carrying.corner
    runner.on_place(681, 1120)
    assert prefs[dc.OVERLAY_POS_PREF] == [681, 1120] and carrying.corner == corner


# --- review of bde97408: nothing stale is replayed, nothing half-read is used ---------------------------------------


def test_a_clean_stop_then_a_start_uses_the_saved_place_not_the_stopped_runner(carrying, prefs):  # noqa: F811
    prefs[dc.OVERLAY_POS_PREF] = [681, 1120]
    carrying.set_main_hidden(True)
    first = FakeRunner.started[0]
    first.engine = SimpleNamespace(x=1290, y=1120, carry=lambda: dict(TRIP))
    carrying.close()  # a clean stop (turned off, the app quitting): nothing to come back to
    carrying.closing = False
    carrying.set_main_hidden(True)
    again = FakeRunner.started[-1]
    assert again is not first and again.home == (681, 1120) and again.carried is None


def test_a_death_is_replayed_once_and_not_when_old(carrying, prefs):  # noqa: F811
    prefs[dc.OVERLAY_POS_PREF] = [681, 1120]
    clock = [100.0]
    carrying._now = lambda: clock[0]  # noqa: SLF001
    carrying.set_main_hidden(True)
    first = FakeRunner.started[0]
    first.engine = SimpleNamespace(x=1290, y=1120, carry=lambda: dict(TRIP))
    first.on_died()
    clock[0] += dc.OVERLAY_RETRY_GAP + 1  # the retry comes no sooner than the gap
    carrying.set_main_hidden(False)
    carrying.set_main_hidden(True)
    second = FakeRunner.started[-1]
    assert second is not first and second.home == (1290, 1120) and second.carried == TRIP
    carrying._stop_runner()  # noqa: SLF001 - a clean stop and a second start: the death was used up
    carrying.set_main_hidden(True)
    third = FakeRunner.started[-1]
    assert third is not second and third.home == (681, 1120) and third.carried is None
    third.engine = SimpleNamespace(x=1290, y=1120, carry=lambda: dict(TRIP))
    third.on_died()
    clock[0] += dc.LAST_PLACE_KEEP + 1  # long after: the saved place, not an old trip
    carrying.set_main_hidden(False)
    carrying.set_main_hidden(True)
    fourth = FakeRunner.started[-1]
    assert fourth is not third and fourth.home == (681, 1120) and fourth.carried is None


def test_a_death_before_the_engine_was_ready_keeps_the_last_good_place(carrying):  # noqa: F811
    carrying.set_main_hidden(True)
    first = FakeRunner.started[0]
    first.engine = SimpleNamespace(x=1290, y=1120, carry=lambda: dict(TRIP))
    first.on_died()
    assert carrying._last_place == (1290, 1120)  # noqa: SLF001
    carrying.runner = Carrying(look="masculine", home=None, on_click=None, on_settle=None)  # no engine yet
    carrying._overlay_died()  # noqa: SLF001
    assert carrying._last_place == (1290, 1120) and carrying._last_carry == TRIP  # noqa: SLF001


def test_a_place_that_is_not_a_number_is_no_place(carrying):  # noqa: F811
    carrying.set_main_hidden(True)
    FakeRunner.started[0].engine = SimpleNamespace(x=float("nan"), y=1120)
    assert carrying._runner_place() is None  # noqa: SLF001


def test_an_off_screen_place_and_goal_land_on_the_monitor() -> None:
    e = _engine(1, home=(9000, 9000))
    assert AREA[0] <= e.x <= AREA[2] - e.size[0] and AREA[1] <= e.y <= AREA[3] - e.size[1]
    e.take({"home_x": 9000.0, "homed_for": 1.0, "goal": -5000.0, "then": "settle"}, 1.0)
    assert e.home_x == AREA[2] - e.size[0]
    goal = e.goal or (e.pending[0] if e.pending else e.warp["dst"] if e.warp else None)
    assert goal is not None and AREA[0] <= goal[0] <= AREA[2] - e.size[0] and AREA[1] <= goal[1] <= AREA[3] - e.size[1]


def test_carry_reads_the_warp_once() -> None:
    class Vanishing(dict):
        """The overlay thread finishes the warp (clears it) right after the first read."""

        def __init__(self, e: Engine, **kw: object) -> None:
            super().__init__(**kw)
            self.e = e

        def __getitem__(self, key: str) -> object:
            value = super().__getitem__(key)
            self.e.warp = None
            return value

    e = _engine(1)
    e.state, e.then = "warp", "settle"
    e.warp = Vanishing(e, dst=(300.0, 1000.0))
    assert e.carry()["goal"] == 300.0


def test_a_late_arrival_never_overwrites_a_drop() -> None:
    from tessellate.core.overlay import runner as runner_mod

    later: list = []
    saved: list = []
    r = runner_mod.OverlayRunner(w=object(), backend=SimpleNamespace(windows=lambda w: []), dispatch=lambda name, fn: later.append(fn))
    r.on_settle = lambda x, y: saved.append(("drop", x, y))
    r.on_place = lambda x, y: saved.append(("place", x, y))
    engine = SimpleNamespace(home_arrivals=1, home=lambda: (300, 1000))
    r._hand_offs(SimpleNamespace(click=None, settled=False, card=None), engine)  # noqa: SLF001 - a trip arrives
    engine.home = lambda: (900, 1000)
    r._hand_offs(SimpleNamespace(click=None, settled=True, card=None), engine)  # noqa: SLF001 - then a drop
    for fn in later:  # the hand-offs run later, on workers
        fn()
    assert saved == [("drop", 900, 1000)]
