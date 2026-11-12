"""E5 (OPEN.md Tier E; INBOX 1692 e, n, d and 1711): the companion's own activities with props, the wind-spirit
travel and the acts weighted by the local hour, on the desk and in the app from one catalogue.

Fixed clocks and seeded streams only: the Mind is ticked with a made-up `now` and an hour; the engine is driven
with a counted `t`; nothing reads the wall clock."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import behaviour as bh  # noqa: E402
from tessellate.core.overlay import extras, faces, presence, props, windspirit  # noqa: E402
from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay.sprites import SpriteSet  # noqa: E402
from tests.test_overlay_ride_1670 import make  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOC = json.loads((ROOT / "frontend" / "companion-catalogue.json").read_text(encoding="utf-8"))
BY_ID = {e["id"]: e for e in DOC["entries"]}
#: A morning, an afternoon, an evening and a night hour, one per part of the day (the catalogue's `phases`).
MORNING, AFTERNOON, EVENING, NIGHT = 8, 14, 19, 2

#: The three new doings: desk act -> (prop, catalogue id, app key).
NEW = {
    "eat_dinner": ("bowl", "act.dinner", "dinner"),
    "blow_bubbles": ("wand", "act.blow_bubbles", "bubbles"),
    "knit_starlight": ("knit", "act.knit_starlight", "knit"),
}


@pytest.fixture(autouse=True)
def _registered() -> None:
    extras.register()


# --- (a) own activities with props ----------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(NEW))
def test_each_new_doing_is_a_prop_act_the_mind_can_pick_and_the_menu_names(name: str) -> None:
    prop, _cid, _key = NEW[name]
    assert name in props.PROP_ACTS or name in props.SPELL_ACTS
    assert props.spec_of(name).prop == prop
    assert name in bh.ACTIVITIES and name in faces.ACT_FACES
    assert props.DOING[name] and "_" not in props.DOING[name] and "\u2014" not in props.DOING[name]
    assert "!" not in props.DOING[name]


@pytest.mark.parametrize("look", ("masculine", "feminine"))
@pytest.mark.parametrize("name", sorted(NEW))
def test_each_new_prop_is_drawn_moves_and_is_fetched_in_steps(look: str, name: str) -> None:
    spec = props.spec_of(name)
    act = bh.ACTIVITIES[name]
    base = SpriteSet(look).frame(act.frame if isinstance(act.frame, str) else act.frame[0][1], 96, False)
    pics = [props.draw(base, (spec.prop, phase, 3), False).bgra for phase in range(spec.steps)]
    assert all(p != base.bgra for p in pics)
    assert len(set(pics)) == spec.steps, "every phase is its own picture (a bubble rises, a needle moves, a spoon lifts)"
    assert props.draw(base, (spec.prop, 0, 1), False).bgra != pics[0]


def test_the_new_doings_are_three_and_carry_a_prop_each() -> None:
    assert len(NEW) >= 3
    assert len({p for p, _c, _k in NEW.values()}) == len(NEW)


def test_the_knit_is_a_presence_spell_by_the_hour() -> None:
    assert presence.SPELLS["knit"].act == "knit_starlight"
    hours = presence.SPELLS["knit"].hours
    assert EVENING in hours and NIGHT not in hours and MORNING not in hours
    rng = random.Random(11)
    picks = [presence.pick_spell(rng, EVENING, "content", []) for _ in range(300)]
    assert "knit" in picks and picks.count("knit") > 20
    assert "knit" not in [presence.pick_spell(rng, MORNING, "content", []) for _ in range(300)]


def test_the_catalogue_says_the_doings_are_built_on_both_sides_with_real_pointers() -> None:
    for name, (_prop, cid, key) in NEW.items():
        e = BY_ID[cid]
        assert e["desk"]["s"] == "built" and e["app"]["s"] == "built", cid
        assert f"acts:{name}" in e["desk"]["names"], cid
        assert e["app"]["names"] == [f"acts:{key}"], cid
        assert e["desk"]["at"].split("#", 1)[1] in (ROOT / e["desk"]["at"].split("#", 1)[0]).read_text(encoding="utf-8")
        assert e["app"]["at"] == f"frontend/js/avatars.js#  {key}: {{ ms:"


# --- (c) acts weighted by the local hour ----------------------------------------------------------------


def test_a_prop_act_takes_the_catalogue_day_weights_at_last() -> None:
    """The props register after the catalogue was read, so they used to carry none of its day weights."""
    tea = BY_ID["act.sip_tea"]["day"]
    f = lambda h: bh.catalogue_factor("sip_tea", "content", h)  # noqa: E731
    assert f(MORNING) > max(f(AFTERNOON), f(EVENING)) > f(NIGHT)
    assert bh.catalogue_factor("sip_tea", "sleepy", NIGHT) == 0 and tea["night"] == 0
    # fishing is for the evening, the stars for the night, a blanket nap for the night
    assert bh.catalogue_factor("go_fishing", "content", EVENING) > bh.catalogue_factor("go_fishing", "content", MORNING)
    assert bh.catalogue_factor("watch_stars", "content", NIGHT) > bh.catalogue_factor("watch_stars", "content", MORNING)
    assert bh.catalogue_factor("blanket_nap", "content", NIGHT) > bh.catalogue_factor("blanket_nap", "content", AFTERNOON)


def test_the_new_doings_follow_the_hour() -> None:
    f = bh.catalogue_factor
    assert f("eat_dinner", "content", EVENING) > f("eat_dinner", "content", AFTERNOON) > f("eat_dinner", "content", MORNING)
    assert f("eat_dinner", "content", EVENING) > 3 * f("eat_dinner", "content", NIGHT)
    assert f("blow_bubbles", "happy", AFTERNOON) > f("blow_bubbles", "happy", MORNING)
    assert f("blow_bubbles", "happy", NIGHT) == 0
    assert f("knit_starlight", "content", EVENING) > f("knit_starlight", "content", MORNING)


def test_ambient_acts_lean_to_their_part_of_the_day() -> None:
    f = bh.catalogue_factor
    assert f("stretch", "content", MORNING) > f("stretch", "content", EVENING)
    assert f("yawn", "content", MORNING) > f("yawn", "content", AFTERNOON)
    assert f("little_dance", "content", AFTERNOON) > f("little_dance", "content", NIGHT)
    assert f("kick_legs", "content", AFTERNOON) > f("kick_legs", "content", NIGHT)  # the leg swing
    assert f("snack", "happy", AFTERNOON) > f("snack", "happy", NIGHT)
    assert f("push_ups", "content", MORNING) > f("push_ups", "content", EVENING)


def _share(hour: int, name: str) -> float:
    """The share of the Mind's table one act holds at `hour`, over a fixed clock (nothing random)."""
    mind = bh.Mind(0.0)
    table = dict(mind.weights(100.0, "walk", hour))
    return table.get(name, 0.0) / sum(table.values())


def test_the_minds_own_table_moves_with_the_hour() -> None:
    assert _share(MORNING, "sip_tea") > 3 * _share(EVENING, "sip_tea")
    assert _share(EVENING, "eat_dinner") > 3 * _share(MORNING, "eat_dinner")
    assert _share(AFTERNOON, "blow_bubbles") > _share(NIGHT, "blow_bubbles")
    assert _share(NIGHT, "sip_tea") == 0.0


def _picks(seed: int, hour: int, hours: int = 6) -> list[str]:
    rng, mind = random.Random(seed), bh.Mind(0.0)
    t, out = 0.0, []
    while t < hours * 3600.0:
        mind.tick(t, hour)
        name = mind.pick(rng, t, "walk", hour)
        mind.did(name, t)
        out.append(name)
        t += rng.uniform(*bh.ACTIVITIES[name].seconds) + 1.0
    return out


def test_seeded_hours_pick_tea_by_morning_and_dinner_by_evening() -> None:
    tea_am = sum(_picks(s, MORNING).count("sip_tea") for s in (1, 2, 3))
    tea_pm = sum(_picks(s, EVENING).count("sip_tea") for s in (1, 2, 3))
    dinner_pm = sum(_picks(s, EVENING).count("eat_dinner") for s in (1, 2, 3))
    dinner_am = sum(_picks(s, MORNING).count("eat_dinner") for s in (1, 2, 3))
    assert tea_am > tea_pm
    assert dinner_pm > dinner_am


def test_the_app_reads_the_same_day_weights_for_the_same_acts() -> None:
    """One table, two readers: the app's factor (`nmb.cat.factor`) is the desk's for each new doing, by part of the day."""
    from tests._cat_node import run

    acts = {key: {"ms": 1, "w": 1, "cool": 0, "poses": ["stand"]} for _p, _c, key in NEW.values()}
    got = run(
        "nmb.cat.load(); await new Promise((r) => setTimeout(r, 20));"
        "const out = {}; for (const a of Object.keys(NAME_MARK_BUDDY_ACTS)) { out[a] = {};"
        " for (const p of ['morning','afternoon','evening','night']) out[a][p] = nmb.cat.factor(a, 'content', p); }"
        "console.log(JSON.stringify(out));",
        acts,
    )
    for name, (_p, cid, key) in NEW.items():
        e = BY_ID[cid]
        for phase, hour in (("morning", MORNING), ("afternoon", AFTERNOON), ("evening", EVENING), ("night", NIGHT)):
            assert got[key][phase] == pytest.approx(e.get("mood", {}).get("content", 1.0) * e["energy"][_energy(phase)] * e.get("day", {}).get(phase, 1.0)), (key, phase)
            assert bh.catalogue_factor(name, "content", hour) == pytest.approx(got[key][phase]), (name, phase)


def _energy(phase: str) -> int:
    return DOC["energy_by_phase"][phase]


# --- (b) wind-spirit travel ----------------------------------------------------------------------------


def _fly(seed: int = 3, to: tuple[float, float] = (120.0, 400.0)):
    """A floater sent on a trip across the screen, drawn at 60 a second on a counted clock: (engine, the views by time)."""
    e, _s = make("masculine", "float", seed, plain=True)
    e.presence = False
    e.big_ready = e.trip_ready = e.climb_ready = e.ex.act_ready = float("inf")
    e.next_ambient = float("inf")
    e.ex.micro.next_at = float("inf")
    t = 0.0
    for _ in range(60):
        t += 0.05
        e.update(t)
    return e, t


def _views(e, t: float, seconds: float, step: float = 0.016):
    seen = []
    end = t + seconds
    while t < end:
        t += step
        e.update(t)
        seen.append((round(t, 3), e.state, e.ex.view(t)[0], e.facing))
    return seen, t


def _settle(e, t: float, cap: float = 20.0):
    """Step until the trip is over (the state leaves drift) and the eddy has had its time: (the views, the clock)."""
    seen, end = [], t + cap
    while e.state == "drift" and t < end:
        more, t = _views(e, t, 0.5)
        seen += more
    more, t = _views(e, t, windspirit.EDDY_FOR + 0.5)
    return seen + more, t


def test_a_gust_of_motes_trails_a_floater_on_its_way() -> None:
    e, t = _fly()
    e._go((e.x - 700.0, e.y), "clock", t)
    seen, _t = _views(e, t, 4.0)
    names = {p[0] for _t, st, p, _f in seen if p}
    assert "gust" in names
    drifting = [p for _t, st, p, _f in seen if st == "drift"]
    assert drifting and sum(1 for p in drifting if p and p[0] == "gust") > 0.5 * len(drifting)
    phases = {p[1] for p in drifting if p and p[0] == "gust"}
    assert len(phases) >= 3, "the motes move"


def test_a_turn_makes_a_spiral_and_the_end_a_settle_eddy() -> None:
    e, t = _fly()
    e._go((e.x + 600.0, e.y), "clock", t)  # one way, then back the other: a turn in the middle of a ride
    seen, t = _views(e, t, 1.2)
    e.goal = (e.x - 500.0, e.y)
    more, t = _settle(e, t)
    seen += more
    kinds = [p[0] for _t, _s, p, _f in seen if p]
    assert "spiral" in kinds
    assert "eddy" in kinds
    first_eddy = next(i for i, (_t, _s, p, _f) in enumerate(seen) if p and p[0] == "eddy")
    assert seen[first_eddy][1] != "drift", "the eddy is where it settles, not while it is still flying"
    last_gust = max(i for i, (_t, _s, p, _f) in enumerate(seen) if p and p[0] == "gust")
    assert last_gust < first_eddy


def test_the_eddy_ends_and_the_ride_leaves_nothing_behind() -> None:
    e, t = _fly()
    e._go((e.x - 500.0, e.y), "clock", t)
    seen, t = _settle(e, t)
    assert any(p and p[0] == "eddy" for _t, _s, p, _f in seen)
    after, _t = _views(e, t, 0.5)
    assert after[-1][2] is None or after[-1][2][0] not in {"gust", "spiral", "eddy"}, "the eddy has gone"
    assert e.ex.wind.next_step(_t) is None, "and nothing is left to wake for"


def test_reduced_motion_rides_no_gust() -> None:
    e, t = _fly()
    e.reduced = True
    e._go((e.x - 500.0, e.y), "clock", t)
    seen, _t = _views(e, t, 4.0)
    assert not [1 for _t, _s, p, _f in seen if p and p[0] in {"gust", "spiral", "eddy"}]


def test_a_walker_has_no_gust() -> None:
    e, _s = make("masculine", "walk", 3, plain=True)
    e.presence = False
    t = 0.0
    for _ in range(60):
        t += 0.05
        e.update(t)
    e._go((e.x - 500.0, e.y), "clock", t)
    seen, _t = _views(e, t, 4.0)
    assert not [1 for _t, _s, p, _f in seen if p and p[0] in {"gust", "spiral", "eddy"}]


def test_the_ride_adds_no_blinks_and_the_turn_blink_keeps_its_gap() -> None:
    """No ferocious blinking: the wind draws motes, never lids; and the engine's own blink at a turn is never nearer another than the least gap."""
    e, t = _fly(seed=5)
    blinks: list[float] = []
    real = e._blink

    def count(now: float, *a, **k):
        blinks.append(now)
        return real(now, *a, **k)

    e._blink = count  # type: ignore[method-assign]
    for k in range(6):  # six turns in a row, back and forth
        e._go((e.x + (600.0 if k % 2 == 0 else -600.0), e.y), "clock", t)
        _s, t = _views(e, t, 1.6)
    gaps = [b - a for a, b in zip(blinks, blinks[1:])]
    assert all(g >= eng.AMBIENT_EVERY[0] - 1e-6 for g in gaps), gaps
    assert len(blinks) <= 1 + int((t - 3.0) / eng.AMBIENT_EVERY[0])
    wind = windspirit.Wind()
    assert not hasattr(wind, "blink")


def test_the_wind_pictures_are_drawn_and_move() -> None:
    base = SpriteSet("masculine").frame("stand", 96, False)
    for name in ("gust", "spiral", "eddy"):
        spec = props.WIND_SPECS[name]
        pics = [props.draw(base, (name, phase, 3), False).bgra for phase in range(spec.steps)]
        assert all(p != base.bgra for p in pics), name
        assert len(set(pics)) == spec.steps, name
        assert props.draw(base, (name, 0, 3), True).bgra != props.draw(base, (name, 0, 3), False).bgra, name


def test_the_wind_is_pure_for_a_fixed_clock() -> None:
    w = windspirit.Wind()
    assert w.next_step(5.0) is None
    ride = windspirit.gust_phase(1.0)
    assert ride == windspirit.gust_phase(1.0) and 0 <= ride < props.WIND_SPECS["gust"].steps
    assert 0 < windspirit.SPIRAL_FOR <= 1.0 and 0 < windspirit.EDDY_FOR <= 1.6


def test_the_wind_sizes_wind_down() -> None:
    sizes = [windspirit.unwind(u / 10.0) for u in range(0, 10)]
    assert sizes == sorted(sizes, reverse=True) and sizes[0] == 3 and sizes[-1] >= 1


# --- the words ------------------------------------------------------------------------------------------


def test_help_lists_the_new_doings_and_the_ride() -> None:
    from tessellate.ai import help_topics_more

    text = json.dumps(help_topics_more.__dict__, default=str).lower()
    for word in ("dinner", "bubbles", "knit", "gust"):
        assert word in text, word
    assert not re.search("[\u2014!]", "".join(props.DOING.values()))


# --- the ride in the app (companion-travel.js `wind`) -----------------------------------------------------

TRAVEL = (ROOT / "frontend" / "js" / "companion-travel.js").read_text(encoding="utf-8")
TRAVEL_CSS = (ROOT / "frontend" / "css" / "companion-travel-lazy.css").read_text(encoding="utf-8")


def _choose(**kw) -> list:
    """`companionTravelChoose` for a hundred fixed rolls (the pure half of the file, run under node as written)."""
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("node is not installed")
    o = {"last": "", "dx": 800, "dy": -300, "size": 64, "reduced": False, "win": [1440, 900], "x0": 900, "x1": 100, "y0": 800}
    o.update(kw)
    pure = TRAVEL[: TRAVEL.index("//: ---- Playing a move")]
    script = pure + f"\nconsole.log(JSON.stringify(Array.from({{length: 100}}, (_, i) => companionTravelChoose({json.dumps(o)}, i / 100))));"
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_the_wind_is_atlas_only_and_a_far_way_only() -> None:
    assert "wind" in _choose(atlas=True)
    assert "wind" not in _choose(atlas=False)
    assert "wind" not in _choose()
    near = {"dx": 90, "dy": 0, "x0": 400, "x1": 310}
    assert set(_choose(atlas=True, **near)) == {"walk"}


def test_the_wind_never_repeats_and_reduced_motion_keeps_the_fade() -> None:
    assert "wind" not in _choose(atlas=True, last="wind")
    assert set(_choose(atlas=True, reduced=True)) == {"fade"}


def test_the_wind_has_a_player_a_sheet_and_the_figure_stays() -> None:
    assert "  wind(buddy, dx, dy, ctx) {" in TRAVEL
    assert "atlas: isAtlasSeed(buddy.dataset.seed)" in TRAVEL
    for cls in ("nmb-gust", "nmb-spiral", "nmb-eddy"):
        assert f".{cls}" in TRAVEL_CSS, cls
        assert f'"{cls}"' in TRAVEL, cls
        assert f"@keyframes {cls}" in TRAVEL_CSS, cls
    wind = TRAVEL[TRAVEL.index("  wind(buddy, dx, dy, ctx) {") :]
    wind = wind[: wind.index("\n  },")]
    figure = wind[: wind.index("const gust")]
    assert "opacity" not in figure  # the figure itself never fades: the weather around it comes and goes
