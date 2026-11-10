"""A seeded one-hour simulation of the desktop companion for INBOX 1670 (the engine and its fakes,
a fixed clock, no Win32). Measures what the owner feels: how much it moves while it is meant to be at
rest, how often it starts something, how long it sits settled, how much of the hour it travels, how
it travels, and how a hang and a landing look.

"Rest" is a state of standing, sitting, sleeping or an act in place (no walk, trip, hang or peek). The
window's `y` also moves by a few px when the frame changes because each frame is lowered so that its
lowest drawn row is on the floor (the feet stay planted, nothing moves on screen); `rest_window_dy`
counts that, `rest_feet_dy` is the drawn feet line (window y plus the frame's lowest row), which is the
travel a person sees. The masculine look has the same foot offset in every standing frame, so there
the two agree."""

from __future__ import annotations

import functools
import random
import statistics
from collections import Counter

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import travel as tv
from tests.test_overlay_ride_1670 import AREA, make

MOVING = ("walk", "drift", "rise", "leap", "fly", "fall", "hop", "crouch", "held", "pressed", "warp")
SETTLED = ("stand", "sit", "sleep")
#: What counts as starting something: an act, a leg of a trip, a vanish, a hang or a peek. A landing, a fall
#: or a reaction to the pointer follows something else and is not counted.
STARTERS = ("walk", "drift", "warp", "hang", "peek", "wave")
#: A few windows, snapped to the right and left of the work area, for the climb and the jump.
WINDOWS = [eng.Perch(1, 1380, 560, 1920), eng.Perch(2, 0, 420, 560)]


def home_at_edge(e: eng.Engine) -> None:
    """Where it lives by default: 100 px in from the right edge, on the taskbar line."""
    e.x = e.home_x = float(AREA[2] - e.size[0] - eng.HOME_INSET)
    e._place_on_floor()
    e.last_x = e.x


def skip_flow(e: eng.Engine) -> None:
    """Leave the wisps' and streams' picture undrawn: a rate sim reads states, acts and positions, never the flow
    view (it was 40 percent of an hour's cost, and the metrics came out identical to the last digit with it off).
    The follow-through itself still steps, so the engine's settled and wake decisions are unchanged. The layered tail's
    view is left undrawn the same way (about a seventh of an hour's cost; no sim reads `out.tail`, and the metrics of
    five seeded hours came out equal with it off)."""
    e._flow_view = lambda *_a, **_k: None
    e._tail_view = lambda *_a, **_k: None


def runs(seq: list[str]) -> int:
    """The longest run of one value in a row."""
    best = cur = 0
    prev = None
    for v in seq:
        cur = cur + 1 if v == prev else 1
        prev = v
        best = max(best, cur)
    return best


@functools.lru_cache(maxsize=None)
def _plain_hour(gait: str, seed: int, secs: float, pointer: bool, look: str, awake: bool) -> dict:
    """The same seeded hour is read by several test files (travel, modes, hang end): one run per worker. Callers only
    read the result."""
    return _simulate(gait, seed, secs, None, pointer, look, awake)


def simulate(
    gait: str, seed: int, secs: float = 3600.0, setup=None, pointer: bool = True, look: str = "masculine",
    awake: bool = True,
) -> dict:
    """One hour. `awake`: the person is about (the long-idle sit and sleep are off), which is the hard case
    for stillness; with it off a quarter hour of no touch ends in a sit and then a sleep."""
    if setup is None:
        return _plain_hour(gait, seed, secs, pointer, look, awake)
    return _simulate(gait, seed, secs, setup, pointer, look, awake)


def _simulate(gait, seed, secs, setup, pointer, look, awake) -> dict:
    saved = eng.IDLE_SIT, eng.IDLE_SLEEP
    if awake:
        eng.IDLE_SIT = eng.IDLE_SLEEP = float("inf")
    try:
        return _run(gait, seed, secs, setup, pointer, look)
    finally:
        eng.IDLE_SIT, eng.IDLE_SLEEP = saved


def _run(gait, seed, secs, setup, pointer, look) -> dict:
    e, _s = make(look, gait, seed)
    skip_flow(e)
    home_at_edge(e)
    e.big_ready, e.trip_ready = 300.0, 120.0
    e.climb_ready = 0.0
    e.set_windows(list(WINDOWS), 0.0)
    if setup:
        setup(e)
    rng = random.Random(seed + 7)
    px, t = 400, 0.0
    next_ptr = rng.expovariate(1 / 25.0)  # the pointer moves on its own clock, not once per wake: a faster wake must not reshuffle the hour
    out = e.update(0.0, (px, 600) if pointer else None)

    def feet(o) -> float:
        # The rest cycle shares one line (the tail tip of a few feminine frames is a row lower than the feet,
        # not a step): its pictures count at the stand's, the window's own y being what the engine moves.
        name = "stand" if o.frame.startswith("idle") else o.frame
        return o.y + e.metrics.get((name, o.flip), (0, 0, 0, 0))[3]

    rest_t = rest_win = rest_feet = rest_changed = moving_t = 0.0
    starts: Counter = Counter()
    spells: list[float] = []
    spell_at: list[tuple[float, float, float, bool]] = []
    on_perch = False
    spell = 0.0
    last_act_start, wakes, hang_wakes = None, 0, 0
    hang_spans: list[tuple[float, float]] = []  # (length, longest stretch with no change of the picture)
    hang_t0 = hang_last = hang_gap = hang_pose = None
    warps: dict[str, list[float]] = {}
    warp_t0 = None
    landings: list[tuple[float, int]] = []
    pending_land: list = []
    prev = (out.x, out.y)
    prev_state, prev_feet = e.state, feet(out)
    while t < secs:
        step = min(max(0.016, (out.wake_ms or 1000) / 1000.0), 1.0)
        t += step
        if pointer and t >= next_ptr:
            px = rng.randint(200, 1700)
            next_ptr = t + rng.expovariate(1 / 25.0)
        out = e.update(t, (px, 600) if pointer else None)
        wakes += 1
        s = e.state
        hang_wakes += s == "hang"
        if s == "act":
            if e.act_started != last_act_start:
                last_act_start = e.act_started
                starts[e.act] += 1
        elif s in STARTERS and s != prev_state:
            starts[s] += 1
        moving = s in MOVING
        moving_t += step if moving else 0.0
        f = feet(out)
        if not moving and prev_state not in MOVING and s not in ("hang", "peek", "emerge"):
            rest_t += step
            rest_win += abs(out.y - prev[1])
            rest_feet += abs(f - prev_feet)
            rest_changed += step if f != prev_feet else 0.0
        if s in SETTLED and (out.x, f) == (prev[0], prev_feet):
            spell += step
            on_perch = e.perch is not None
        else:
            if spell > 0:
                spells.append(spell)
                spell_at.append((prev[0], prev[1], spell, on_perch))
            spell = 0.0
        if s == "hang":
            if hang_t0 is None:
                hang_t0 = hang_last = t
                hang_gap, hang_pose = 0.0, out.pose
            if out.pose != hang_pose:
                hang_gap = max(hang_gap, t - hang_last)
                hang_last, hang_pose = t, out.pose
        elif hang_t0 is not None:
            hang_gap = max(hang_gap, t - hang_last)
            hang_spans.append((t - hang_t0, hang_gap))
            hang_t0 = None
        if s == "warp" and warp_t0 is None:
            warp_t0, warp_kind = t, e.warp["kind"] if e.warp else "?"
        elif s != "warp" and warp_t0 is not None:
            warps.setdefault(warp_kind, []).append(t - warp_t0)
            warp_t0 = None
        if out.settled:
            pending_land.append([t, f, f, 0])
        for L in pending_land:
            if t - L[0] <= 3.0:
                L[1], L[2] = min(L[1], f), max(L[2], f)
                L[3] += 1 if (s == "land" and prev_state != "land") or (s == "act" and prev_state != "act") else 0
        for L in [L for L in pending_land if t - L[0] > 3.0]:
            landings.append((L[2] - L[1], L[3]))
            pending_land.remove(L)
        prev, prev_state, prev_feet = (out.x, out.y), s, f
    if spell > 0:
        spells.append(spell)
        spell_at.append((prev[0], prev[1], spell, on_perch))
    k = e._scale()
    area = e.current_monitor().area
    # A rest on a window top is a visit (INBOX 1683 g), not a rest spot of the screen: counted apart.
    def on_window(x, y) -> bool:
        return any(w.left <= x + e.size[0] / 2 <= w.right and -80 <= y + e.size[1] - w.top <= 30 for w in WINDOWS)

    def under_window(x, y) -> bool:
        # Where it lands after hopping off a window it visited: down in the floor band under that window
        # (INBOX 1683 g), not mid-air or beside it; a rest higher than two edge zones over the floor still counts.
        low = y >= e.floor_y() - 2 * tv.EDGE_ZONE * k
        return low and any(w.left <= x + e.size[0] / 2 <= w.right and y >= w.top + e.size[1] for w in WINDOWS)

    rests = [(x, y) for x, y, d, p in spell_at if d >= 30.0 and not p and not on_window(x, y)]
    floor = e.floor_y()
    legs = list(getattr(e, "legs", []))
    modes = list(getattr(e, "modes", []))
    return {
        "rest_window_dy_per_min": rest_win / max(rest_t / 60.0, 1e-9),
        "rest_feet_dy_per_min": rest_feet / max(rest_t / 60.0, 1e-9),
        "rest_change_share": rest_changed / max(rest_t, 1e-9),
        "starts_per_10min": sum(starts.values()) / (secs / 600.0),
        "starts": dict(starts),
        "spell_mean": statistics.fmean(spells) if spells else 0.0,
        "spell_median": statistics.median(spells) if spells else 0.0,
        "moving_share": moving_t / secs,
        "wakes_per_min": wakes / (secs / 60.0),
        "hang_wakes_per_min": hang_wakes / (secs / 60.0),
        "hangs": hang_spans,
        "trips": e.trips,
        "warps": warps,
        "landings": landings,
        "modes": modes,
        "legs": legs,
        "walked_through_middle": [
            leg for leg in legs if leg[0] in ("walk", "glide", "climb") and tv.crosses_middle(leg[1], leg[2], area, e.size[0])
        ],
        "rest_spots_off_edge": [
            (x, y) for x, y in rests
            if not (tv.in_edge_zone(x, area, e.size[0], k) or abs(y - floor) <= tv.EDGE_ZONE * k or under_window(x, y))
        ],
        "rest_spots_in_middle": [(x, y) for x, y in rests if tv.in_middle(x, area, e.size[0])],
        "rest_spots": len(rests),
    }
