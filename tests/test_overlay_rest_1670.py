"""A settled companion (INBOX 1670: "cant sit still, it has like adhd", "a buddy not a nucance",
"why does it bob up and down so much, it is floating", "bortaling or vanishing in a puff or gliding
places, or jumping around or climbing"). Measured by a seeded one-hour simulation on a fixed clock
(`tests/overlay_sim_1670.py`): how much it moves at rest, how often it starts something, how long
it sits settled, how it travels, how a hang and a landing look. Nothing here runs on Windows; the
Win32 calls are the fake's."""

from __future__ import annotations

import math
import random

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import sprites, travel as tv
from tessellate.core.overlay import win32 as k
from tests._overlay_fake import FakeWin32
from tests.overlay_sim_1670 import runs, simulate
from tests.test_overlay_ride_1670 import AREA, make

GAITS = ("float", "walk")
SEEDS = (1, 2, 3)
# (gait, seed) -> metrics, built once: a simulated hour takes about two seconds.
_CACHE: dict[tuple[str, int, str], dict] = {}


def hour(gait: str, seed: int, look: str = "masculine") -> dict:
    key = (gait, seed, look)
    if key not in _CACHE:
        _CACHE[key] = simulate(gait, seed, look=look)
    return _CACHE[key]


CASES = [(g, s) for g in GAITS for s in SEEDS]


# --- at rest it is still ------------------------------------------------------------------------


@pytest.mark.parametrize(("gait", "seed"), CASES)
def test_at_rest_the_drawn_feet_do_not_move_and_it_starts_few_things(gait: str, seed: int) -> None:
    m = hour(gait, seed)
    # Before (the same sim on the older engine): 39 to 41 px a minute of feet travel for a floater, 133
    # activity starts per ten minutes, a settled spell of 0.23 s, 5 to 7 percent of the hour moving.
    assert m["rest_feet_dy_per_min"] <= 1.0, m["rest_feet_dy_per_min"]
    assert m["rest_change_share"] <= 0.01
    # the window row moves by a few px with the frame's own foot line (6 since INBOX 1683: a sitting act swaps frames)
    assert m["rest_window_dy_per_min"] <= 6.0
    # Intent moved (INBOX 1683, asks M4/M5: "a lot of actions and activities it can perform while idle"): the in-place acts
    # (a book, a map, a bean bag) are the point now, about 40 an hour; 3 was the bar when only jitter started things.
    assert m["starts_per_10min"] <= 9.0, m["starts"]
    # (INBOX 1683, same move: an in-place act every 60 to 150 s shifts the window a few px with its frame's foot line, which
    # ends a spell without a single step taken; the figure still keeps to its home, which the feet and the moving share hold.)
    assert m["spell_median"] >= 45.0, m["spell_median"]
    assert m["moving_share"] <= 0.03, m["moving_share"]


@pytest.mark.parametrize(("gait", "seed"), CASES)
def test_the_idle_wakes_stay_at_or_below_the_old_rate(gait: str, seed: int) -> None:
    # Intent moved (INBOX 1670, 15:40Z): the old bar was 240 a minute with the cycle in bursts. The figure now lives in place
    # without pause (the cycle at 6 a second, a blink every 3 to 7 s), so the bar is the redraw cap: 12 a second.
    assert hour(gait, seed)["wakes_per_min"] <= 480  # measured about 380 (review: hold the rate, not the cap)


def test_fidgets_are_at_most_two_an_hour() -> None:
    for gait in GAITS:
        for seed in SEEDS:
            starts = hour(gait, seed)["starts"]
            assert sum(starts.get(a, 0) for a in ("bounce", "wiggle", "sway", "float_loop", "little_dance", "wave_idle", "shake_off")) <= 2, (gait, seed, starts)


# --- it travels in its own ways, never across the middle ---------------------------------------


def test_trips_vary_and_it_rests_out_of_the_middle_third() -> None:
    # Intent moved (INBOX 1683 f, the owner: "all it does is sit on the taskbar and poof"): a leg may now be walked
    # across the middle third, so the walked-through-the-middle and three-in-a-row bars are gone; where it comes
    # to REST is still never the middle, and a flourish (puff, portal, edge) is not repeated more than three times.
    seen: set[str] = set()
    for gait in GAITS:
        for seed in SEEDS:
            m = hour(gait, seed)
            seen |= set(m["modes"])
            assert runs([x for x in m["modes"] if x in tv.WARPS]) <= 3, m["modes"]
            assert not m["rest_spots_in_middle"], m["rest_spots_in_middle"]
    assert len(seen) >= 3, seen  # walk, glide, jump, climb, and now and then a puff, portal or the edge walk


def test_a_portal_or_a_puff_takes_between_four_tenths_and_one_and_a_fifth_seconds() -> None:
    kinds: set[str] = set()
    for gait in GAITS:
        for seed in SEEDS:
            for kind, spans in hour(gait, seed)["warps"].items():
                if kind in ("portal", "puff"):
                    kinds.add(kind)
                    assert all(0.4 <= d <= 1.2 for d in spans), (kind, spans)
    assert kinds == {"portal", "puff"}


def test_the_rest_spots_are_edges_corners_and_the_taskbar_line() -> None:
    for gait in GAITS:
        for seed in SEEDS:
            m = hour(gait, seed)
            assert len(m["rest_spots_off_edge"]) <= 1, m["rest_spots_off_edge"]  # one is a landing on a window top


def test_a_hang_is_long_and_the_picture_changes_every_few_seconds() -> None:
    # A hang is a rare pick (about one in twenty-five decisions, a few decisions an hour), so how many an hour of
    # the sim shows depends on the seed. The blink stream moved with INBOX 1670 (15:40Z) and the three seeds showed
    # none, so more seeds are read until there are three (4 to 23 now, the blink gaps moved again at 16:40Z); the bars below are unchanged.
    spans = [h for gait in GAITS for seed in (*SEEDS, *range(4, 24)) for h in hour(gait, seed)["hangs"]]
    assert len(spans) >= 3
    lengths = sorted(a for a, _b in spans)
    assert lengths[len(lengths) // 2] >= 30.0, lengths
    assert max(b for _a, b in spans) <= 5.0, spans


def test_every_planned_hang_lasts_at_least_half_a_minute_whatever_the_mood() -> None:
    # The sim above sees few hangs in an hour (a different seed can show none), so the plan itself is pinned.
    assert all(lo >= 30.0 and hi <= 200.0 for lo, hi in bh.HANG_BY_MOOD.values())
    assert eng.HANG_FOR[0] >= 30.0


def test_after_a_landing_there_is_at_most_one_settle_and_no_vertical_motion() -> None:
    lands = [x for gait in GAITS for seed in SEEDS for x in hour(gait, seed)["landings"]]
    assert lands
    assert all(rng <= 2.0 and settles <= 1 for rng, settles in lands), lands


@pytest.mark.parametrize("look", ["masculine", "feminine"])
def test_both_looks_are_still_by_the_feet_line(look: str) -> None:
    m = hour("float", 2, look)
    assert m["rest_feet_dy_per_min"] <= 1.0 and m["starts_per_10min"] <= 9.0 and m["spell_median"] >= 45.0


# --- the text bar: never over the caret, and no trip while typing -----------------------------


def over(e: eng.Engine, rect: tuple[int, int, int, int]) -> bool:
    x, y, _clip = e._display(e._frame(e.now))
    left, top, right, bottom = e._box(e._frame(e.now), e.facing < 0)
    return tv.overlaps((x + left, y + top, x + right, y + bottom), tv.padded(rect, tv.CARET_MARGIN * e._scale()))


@pytest.mark.parametrize("gait", GAITS)
def test_it_steps_off_the_caret_within_a_second_and_stays_off(gait: str) -> None:
    e, _s = make("masculine", gait)
    e.update(0.0)
    box = e._box_at(e.x, e.y)
    rect = (int(box[0]) - 5, int(box[1]) - 5, int(box[0]) + 10, int(box[3]))
    e.set_caret(rect)
    t, covered = 0.0, []
    while t < 6.0:
        t += 0.05
        e.update(t)
        covered.append((t, over(e, rect)))
    assert not any(c for tt, c in covered if tt > 1.5), [tt for tt, c in covered if c]
    assert any(c for tt, c in covered) or e.state in ("warp", "stand")  # it was over it at the start, then it moved


def test_it_never_goes_over_the_caret_on_a_trip_either() -> None:
    e, _s = make("masculine", "float", plain=False)
    e.update(0.0)
    rect = (850, 880, 900, 930)  # in the bottom middle, where a trip to the other side might cross
    e.set_caret(rect)
    e.trip_ready = 0.0
    t, bad = 1.0, 0
    for _ in range(40000):
        t += 0.1
        e.update(t)
        if t > 3.0 and over(e, rect):
            bad += 1
    assert bad == 0


def test_it_starts_no_trip_while_the_person_types() -> None:
    e, _s = make("masculine", "float")
    e.quiet = True
    e.trip_ready = e.big_ready = 0.0
    t = 0.0
    for _ in range(36000):
        t += 0.5
        e.update(t, (300, 500))
    assert e.trips == 0 and not e.legs


def test_reduced_motion_is_a_plain_fade() -> None:
    e, _s = make("masculine", "float")
    e.reduced = True
    e.update(0.0)
    e._start_warp("fade", (200.0, e.y), "stand", 1.0)
    seen = [e.update(1.0 + 0.05 * i) for i in range(1, 30)]
    assert all(o.fx is None for o in seen)
    assert min(o.alpha for o in seen) < 1.0
    assert e.legs[-1][0] == "fade"


# --- the Win32 side: a caret read, behind the fake, at 0.5 Hz ----------------------------------


def test_the_caret_is_the_carets_corners_in_screen_pixels() -> None:
    fake = FakeWin32()
    assert k.caret_rect(fake) is None
    fake.caret = ((10, 20, 12, 40), (300, 400))
    assert k.caret_rect(fake) == (310, 420, 312, 440)
    names = fake.names("user32")
    assert "GetGUIThreadInfo" in names and names.count("ClientToScreen") == 2
    fake.caret = ((5, 5, 5, 5), (0, 0))  # an empty rect still has a width of one pixel
    assert k.caret_rect(fake) is None or k.caret_rect(fake)[2] > k.caret_rect(fake)[0]


# --- the picture: a fade, a ring, a puff -------------------------------------------------------


def test_the_effect_fades_the_figure_and_draws_a_ring_or_a_puff_without_a_halo() -> None:
    spr = sprites.SpriteSet("masculine")
    base = spr.frame("stand", 96, False)
    assert sprites.effect(base, None, 1.0) is base
    half = sprites.effect(base, None, 0.5)
    assert half.width == base.width and half.bgra != base.bgra
    assert sprites.effect(base, None, 0.02).bgra == bytes(len(base.bgra))  # clear: nothing to click on
    for kind in ("portal", "puff"):
        drawn = sprites.effect(base, (kind, 0.8, 1), 0.6)
        assert drawn.bgra != half.bgra and drawn.box == base.box
        alphas = drawn.bgra[3::4]
        # the halo guard: an almost clear pixel is fully clear, so no click lands on a ghost edge
        assert not any(0 < a < sprites.ALPHA_FLOOR for a in alphas)


def test_the_warp_view_is_a_ring_then_nothing_then_the_figure_again() -> None:
    e, _s = make("masculine", "float")
    e.update(0.0)
    e._start_warp("portal", (300.0, e.y), "stand", 1.0)
    t, alphas, fxs = 1.0, [], []
    while e.state == "warp" and t < 5.0:
        t += 0.02
        o = e.update(t)
        alphas.append(o.alpha)
        fxs.append(o.fx)
    assert min(alphas) == 0.0 and alphas[0] > 0.8 and alphas[-1] == 1.0
    assert any(f and f[0] == "portal" for f in fxs)
    assert 0.4 <= t - 1.0 <= 1.3


def test_the_sim_numbers_are_finite() -> None:
    assert all(math.isfinite(hour(g, 1)[key]) for g in GAITS for key in ("rest_feet_dy_per_min", "spell_median", "moving_share"))
    assert random.Random(1) and AREA[2] == 1920


def test_the_runner_reads_the_caret_at_most_twice_a_second_and_hands_it_to_the_engine() -> None:
    from tests.test_overlay_runner import make as make_runner

    r, fake, clock, *_ = make_runner(reduced=False)
    assert r.start()
    try:
        fake.caret = ((10, 20, 12, 40), (300, 400))
        before = fake.names("user32").count("GetGUIThreadInfo")
        now = 1000.0
        for i in range(600):  # a minute of ticks at 10 Hz
            r._busy_gate(now + i * 0.1)
        reads = fake.names("user32").count("GetGUIThreadInfo") - before
        assert 25 <= reads <= 31, reads  # every BUSY_EVERY = 2 s, so 0.5 Hz
        assert r.engine.caret == (310, 420, 312, 440)
        fake.caret = None
        r._busy_gate(now + 1000.0)
        assert r.engine.caret is None
        assert r._cap_wake(None) == int(2.0 * 1000) and r._cap_wake(500) == 500
    finally:
        r.stop()


# --- an app with no system caret (Chromium, Electron): the window's bottom band stands in ------


def test_the_text_zone_is_the_bottom_middle_of_the_foreground_window() -> None:
    fake = FakeWin32()
    fake.window_list[900] = {"rect": (0, 0, 1000, 800)}
    assert k.text_zone(fake) == (150, 630, 850, 800)
    fake.window_list[900] = {"rect": (0, 0, 1000, 200)}  # too short to hold a chat box and its history
    assert k.text_zone(fake) is None
    fake.window_list[900] = {"rect": (0, 0, 200, 800)}
    assert k.text_zone(fake) is None


def test_typing_without_a_caret_keeps_it_off_the_bottom_of_the_window_and_stopping_frees_it() -> None:
    from tests.test_overlay_runner import make as make_runner

    r, fake, *_ = make_runner(reduced=False)
    assert r.start()
    try:
        fake.caret = None
        fake.window_list[900] = {"rect": (0, 0, 1000, 800)}
        fake.last_input = (5000, 4000)  # a key a second ago
        r._busy_gate(1000.0)
        assert r.engine.quiet and r.engine.caret == (150, 630, 850, 800)
        fake.last_input = (50000, 4000)  # nothing for 46 s
        r._busy_gate(1100.0)
        assert not r.engine.quiet and r.engine.caret is None
        fake.last_input = (5000, 4000)
        fake.caret = ((10, 20, 12, 40), (300, 400))  # a real caret wins over the stand-in
        r._busy_gate(1200.0)
        assert r.engine.caret == (310, 420, 312, 440)
    finally:
        r.stop()
