"""INBOX 1692, the owner 2026-11-08: "the desktop companion still doesnt have various ways of moving ... I just want more life
to it" (think a companion that is there and present but not in the way). Fixed clock, seeded randomness; nothing here ran on
real Windows."""
from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import sprites as sp  # noqa: E402


def blob(w: int = 132, h: int = 151) -> sp.Frame:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((20, 0, w - 20, h - 1), fill=(200, 180, 255, 255))
    return sp.Frame(w, h, sp.premultiplied_bgra(image), 0, 0, (20, 0, w - 19, h))


def border_alpha(frame: sp.Frame) -> int:
    """The largest alpha on the canvas' outermost row or column."""
    from PIL import Image

    img = Image.frombytes("RGBA", (frame.width, frame.height), frame.bgra, "raw", "BGRa")
    a = img.getchannel("A")
    w, h = a.size
    ring = [a.getpixel((x, y)) for x in range(w) for y in (0, h - 1)] + [a.getpixel((x, y)) for y in range(h) for x in (0, w - 1)]
    return max(ring)


@pytest.mark.parametrize("kind", ["portal", "puff", "blink", "cloud", "bubble"])
def test_an_effect_at_full_strength_sits_inside_its_canvas(kind: str) -> None:
    """The ring spanned y -0..156 of a 151 px canvas (clipped top and bottom); every effect has its room now."""
    f = sp.effect(blob(), (kind, 1.0, 1), 1.0)
    assert border_alpha(f) == 0, kind
    assert f.width > 132 and f.height > 151
    # the window keeps its place: the figure sits at the same screen spot through the grown canvas
    assert (f.box[0] - f.pad_x, f.box[1] - f.pad_y) == (20, 0)


def test_no_effect_leaves_the_canvas_alone() -> None:
    f = blob()
    assert sp.effect(f, None, 1.0) is f
    faded = sp.effect(f, None, 0.5)
    assert (faded.width, faded.height, faded.pad_x) == (132, 151, 0)


def test_a_cloud_is_drawn_under_the_feet_not_over_the_body() -> None:
    from PIL import Image

    f = sp.effect(blob(), ("cloud", 1.0, 1), 1.0)
    img = Image.frombytes("RGBA", (f.width, f.height), f.bgra, "raw", "BGRa")
    # a body pixel keeps the body's colour (premultiplied back), and there is cloud below the box
    mid = img.getpixel((f.box[0] + 10, (f.box[1] + f.box[3]) // 2))
    assert mid[3] == 255 and mid[2] > 240 and mid[0] < 215, mid
    below = img.getchannel("A").crop((f.box[0], f.box[3] + 2, f.box[2], f.height)).getextrema()[1]
    assert below > 0


# --- travel you can see (INBOX 1692: "various ways of moving ... a portal or like magic ... float on a cloud") -------------

import random  # noqa: E402

from tessellate.core.overlay import travel as tv  # noqa: E402
from tests.test_overlay_moves import FLOOR, make  # noqa: E402


def ride(mode: str, seed: int = 3):
    e = make(seed=seed)
    e.plain_legs = False
    e.x = 100.0
    e._place_on_floor()
    e._start_warp(mode, (1500.0, float(FLOOR)), "stand", 1.0)
    t, xs, fx, total = 1.0, [], [], e.warp["w"].total
    while e.state == "warp" and t < 10.0:
        t += 0.016
        out = e.update(t)
        xs.append(out.x)
        fx.append(out.fx)
    return e, xs, fx, t - 1.0, total


@pytest.mark.parametrize("mode", ["cloud", "bubble"])
def test_a_ride_carries_it_in_view_without_a_jump(mode: str) -> None:
    e, xs, fx, took, total = ride(mode)
    assert took >= 1.5, took  # long enough to be seen
    steps = [abs(b - a) for a, b in zip(xs, xs[1:])]
    assert max(steps) < 40, max(steps)  # never a cut: a few px a frame all the way
    assert all(f is not None and f[0] == mode for f in fx[:-2]), fx[:3]
    assert abs(xs[len(xs) // 2] - 800) < 700 and xs[-1] > 1400


def test_a_blink_is_a_vanish_with_sparkles_that_takes_a_moment() -> None:
    e, xs, fx, took, total = ride("blink")
    assert took >= 1.4 and e.x > 1400
    assert any(f and f[0] == "blink" and f[1] > 0.9 for f in fx)


def test_fx_strength_is_rounded_to_sixteenths_so_a_warp_builds_few_pictures() -> None:
    for mode in ("portal", "puff", "blink", "cloud", "bubble"):
        _e, _xs, fx, _t, _total = ride(mode)
        pics = {f for f in fx if f}
        assert all(abs(f[1] * 16 - round(f[1] * 16)) < 1e-9 for f in pics), mode
        assert len(pics) <= 3 * 16 + 4, (mode, len(pics))


def test_the_caret_move_is_never_the_same_twice() -> None:
    rng, seen, last = random.Random(4), set(), []
    for _ in range(300):
        m = tv.caret_move(rng, last)
        assert not last or m != last[-1]
        seen.add(m)
        last.append(m)
    assert seen == {"blink", "portal", "puff"}


def test_stepping_off_the_caret_is_not_always_a_puff() -> None:
    kinds = set()
    for seed in range(12):
        e = make(seed=seed)
        e.plain_legs = False
        e.x = 900.0
        e._place_on_floor()
        e.update(1.0)
        e.set_caret((e.x - 30, e.y - 30, e.x + e.size[0] + 30, e.y + e.size[1] + 30))
        e.update(2.0)
        if e.warp:
            kinds.add(e.warp["kind"])
    assert len(kinds) >= 2, kinds


# --- presence spells: it is there and doing something, not minutes of standing --------------------------------------------

import functools  # noqa: E402
import statistics  # noqa: E402
from collections import Counter  # noqa: E402

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import presence as pr  # noqa: E402
from tessellate.core.overlay import props  # noqa: E402
from tests.overlay_sim_1670 import WINDOWS, home_at_edge  # noqa: E402
from tests.test_overlay_ride_1670 import make as make_float  # noqa: E402

SEG = 1500.0  # seconds simulated per hour of the day below (a quarter of the real hour; rates are scaled)


@functools.lru_cache(maxsize=None)
def spell_run(seed: int, hours: tuple[int, ...], caret: tuple[int, int, int, int] | None = None) -> dict:
    """`SEG` seconds at each hour in `hours`, awake, roam on, windows about, Activity usual (fixed clock)."""
    saved = eng.IDLE_SIT, eng.IDLE_SLEEP
    eng.IDLE_SIT = eng.IDLE_SLEEP = float("inf")
    try:
        e, _ = make_float("masculine", "float", seed)
        home_at_edge(e)
        r0 = random.Random(seed)
        e.big_ready, e.trip_ready, e.climb_ready = r0.uniform(*eng.BIG_FIRST), r0.uniform(*eng.TRIP_FIRST), eng.CLIMB_FIRST
        e.set_windows(list(WINDOWS), 0.0)
        if caret:
            e.set_caret(caret)
        rng = random.Random(seed + 7)
        px, t = 400, 0.0
        out = e.update(0.0, (px, 600))
        stand = spell_t = 0.0
        prev = None
        changes = 0
        near = 1e9
        k = e._scale()
        for i, hour in enumerate(hours):
            e.hour = hour
            end = SEG * (i + 1)
            while t < end:
                step = min(max(0.016, (out.wake_ms or 1000) / 1000.0), 1.0)
                t += step
                if rng.random() < step / 25.0:
                    px = rng.randint(200, 1700)
                out = e.update(t, (px, 600))
                stand += step if e.state == "stand" else 0.0
                if e.state == "act" and e.spell is not None and e.act == e.spell["act"]:
                    key = (out.frame, out.flip, out.pose, out.fx, out.alpha, out.flow, out.prop, out.face)
                    spell_t += step
                    changes += key != prev
                    prev = key
                    if caret:
                        box = e._box_at(e.x, e.y, out.frame)
                        room = props.ROOM * e.size[1]
                        mine = (box[0] - room, box[1] - room, box[2] + room, box[3] + room)
                        keep = tv.padded(tuple(float(c) for c in caret), tv.CARET_MARGIN * k)
                        if tv.overlaps(mine, keep):
                            near = min(near, -1.0)
                else:
                    prev = None
        return {"stand": stand / (SEG * len(hours)) * 60.0, "spells": list(e.spells), "pics": changes / max(spell_t, 1.0), "spell_share": spell_t / (SEG * len(hours)), "near": near, "legs": list(e.legs), "busy_spell": spell_t}
    finally:
        eng.IDLE_SIT, eng.IDLE_SLEEP = saved


def test_it_stands_far_less_it_is_doing_something() -> None:
    mins = [spell_run(s, (10, 11))["stand"] for s in (1, 2)]
    assert statistics.fmean(mins) <= 18.0, mins  # 50 minutes of every hour before


def test_a_spell_lasts_minutes_and_they_differ_through_the_evening() -> None:
    r = spell_run(2, (17, 18, 19))
    lengths = [n[2] for n in r["spells"]]
    assert statistics.median(lengths) >= 120.0, lengths
    assert len({n[0] for n in r["spells"]}) >= 4, [n[0] for n in r["spells"]]
    assert r["spell_share"] >= 0.5, r["spell_share"]


def test_a_spell_costs_a_few_pictures_a_second_not_a_stream() -> None:
    assert spell_run(2, (17, 18, 19))["pics"] <= 4.0


@pytest.mark.parametrize("hour", [22, 7, 14, 18])
def test_the_spell_suits_the_hour(hour: int) -> None:
    rng, seen = random.Random(hour), Counter()
    for _ in range(300):
        seen[pr.pick_spell(rng, hour, "content", [])] += 1
    assert set(seen) <= set(pr.spells_for(hour)), seen
    night = {"doze", "stars", "plant"}
    if hour == 22:
        assert set(seen) <= night and seen["doze"] > 0 and seen["stars"] > 0
    if hour == 7:
        assert seen["tea"] > seen["plant"]


def test_a_spell_is_never_the_one_before() -> None:
    rng, last = random.Random(3), []
    for _ in range(200):
        n = pr.pick_spell(rng, 14, "curious", last)
        assert not last or n != last[-1]
        last.append(n)


def test_every_spell_runs_a_prop_act_that_draws() -> None:
    eng.extras.register()
    for name, s in pr.SPELLS.items():
        assert props.spec_of(s.act) is not None, name
        assert eng.bh.BASE_WEIGHT.get(s.act, 0) >= 0 and s.act in eng.bh.ACTIVITIES, name
    for act in props.SPELL_ACTS:
        assert eng.bh.BASE_WEIGHT[act] == 0  # the mind never picks these by itself


def test_a_spell_prop_is_fetched_in_seconds_not_a_tenth_of_minutes() -> None:
    length = 300.0
    assert props.view("sip_tea", 1.0 / length * 10, 10.0, length)[2] == 3  # whole 10 s in
    assert props.view("sip_tea", 1.0 / length, 1.0, length) is None or props.view("sip_tea", 1.0 / length, 1.0, length)[2] <= 2
    assert props.view("sip_tea", 0.5, 150.0, length)[2] == 3
    assert props.view("sip_tea", 0.99, 297.0, length)[2] <= 2


def test_the_new_props_draw_inside_a_grown_canvas() -> None:
    f = blob()
    for name in ("stars", "blanket", "plant"):
        out = props.draw(f, (name, 1, 3), False)
        assert out.width > f.width and out.height > f.height, name
        assert border_alpha(out) == 0, name
        assert (out.box[0] - out.pad_x, out.box[1] - out.pad_y) == (f.box[0], f.box[1])


def test_a_spell_keeps_its_prop_clear_of_the_text_box() -> None:
    caret = (900, 880, 903, 900)
    r = spell_run(3, (11, 12), caret)
    assert r["near"] >= 0.0, "a spell's drawn box (prop included) touched the padded caret"


def test_typing_does_not_freeze_the_spell() -> None:
    quiet = spell_run(3, (11, 12), (900, 880, 903, 900))
    assert quiet["busy_spell"] >= 0.4 * SEG * 2, quiet["busy_spell"]  # it carries on in place while the caret is there
