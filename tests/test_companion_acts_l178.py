"""L178: the catalogue's ten idle acts that neither companion had, built on both from the one table.

Definition of done (L178): every `idle_act` in `frontend/companion-catalogue.json` is built on both sides (it was 10
missing on both before this), each prop act draws its prop in phases on the desk and in the app, each has its pose in
atlas-lazy.css and its loop inside the motion gate, the menu names what it is doing, and both readers weigh it by the
same mood, energy and part of the day. Fixed clocks only (the factor takes an hour or a phase)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import behaviour as bh  # noqa: E402
from tessellate.core.overlay import extras, faces, props  # noqa: E402
from tessellate.core.overlay.sprites import SpriteSet  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOC = json.loads((ROOT / "frontend" / "companion-catalogue.json").read_text(encoding="utf-8"))
BY_ID = {e["id"]: e for e in DOC["entries"]}
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")
HOURS = {"morning": 8, "afternoon": 14, "evening": 19, "night": 2}

#: desk act -> (prop or None for a plain act, catalogue id, app key)
NEW = {
    "cloud_pillow": ("cloud", "act.cloud_pillow", "cloudpillow"),
    "paper_plane": ("plane", "act.paper_plane", "plane"),
    "conduct": ("baton", "act.conduct", "conduct"),
    "sketch_view": ("sketch", "act.sketch_view", "sketch"),
    "kneel_look": ("speck", "act.kneel_look", "kneel"),
    "lean_on_edge": ("ledge", "act.lean_on_edge", "leanedge"),
    "tail_chase": (None, "act.tail_chase", "tailchase"),
    "tail_stretch": (None, "act.tail_stretch", "tailstretch"),
    "balance_walk": (None, "act.balance_walk", "balance"),
    "stargaze_awake": (None, "act.stargaze_awake", "skyfloat"),
}


@pytest.fixture(autouse=True)
def _registered() -> None:
    extras.register()


#: Played inside the desk's hang (the engine's one-hand path, not the Mind's table): BACKLOG section 15, "Desk hang acts".
IN_THE_HANG = {"act.sloth", "act.hang_by_feet"}


def test_no_idle_act_in_the_catalogue_is_missing_on_either_side() -> None:
    gone = [e["id"] for e in DOC["entries"] if e["kind"] == "idle_act" and "missing" in (e["app"]["s"], e["desk"]["s"])]
    assert sorted(gone) == sorted(IN_THE_HANG), gone


def test_the_chair_is_the_desks_too() -> None:
    assert props.spec_of("chair").prop == "chair" and props.spec_of("chair").under
    e = BY_ID["act.chair"]
    assert e["desk"]["s"] == "built" and e["desk"]["names"] == ["acts:chair"]
    base = SpriteSet("feminine").frame("sit", 96, False)
    assert len({props.draw(base, ("chair", k, 3), False).bgra for k in range(2)}) == 2


@pytest.mark.parametrize("name", sorted(NEW))
def test_each_is_an_act_the_desk_mind_can_pick_and_the_menu_names(name: str) -> None:
    prop = NEW[name][0]
    if prop:
        assert props.spec_of(name).prop == prop
    else:
        assert name in props.PLAIN_ACTS
    assert name in bh.ACTIVITIES and name in faces.ACT_FACES and bh.BASE_WEIGHT[name] > 0
    word = props.DOING[name]
    assert word and "_" not in word and not re.search("[\u2014!]", word)


@pytest.mark.parametrize("look", ("masculine", "feminine"))
@pytest.mark.parametrize("name", sorted(n for n, v in NEW.items() if v[0]))
def test_each_desk_prop_is_drawn_and_moves(look: str, name: str) -> None:
    spec = props.spec_of(name)
    act = bh.ACTIVITIES[name]
    base = SpriteSet(look).frame(act.frame if isinstance(act.frame, str) else act.frame[0][1], 96, False)
    pics = [props.draw(base, (spec.prop, phase, 3), False).bgra for phase in range(spec.steps)]
    assert all(p != base.bgra for p in pics)
    assert len(set(pics)) == spec.steps, "every phase is its own picture"
    assert props.draw(base, (spec.prop, 0, 1), False).bgra != pics[0], "fetched in steps"
    assert props.draw(base, (spec.prop, 0, 3), True).bgra != pics[0], "drawn to the way it faces"


def test_the_new_props_are_their_own() -> None:
    mine = [v[0] for v in NEW.values() if v[0]]
    old = {s.prop for n, (s, _a, _w) in props.PROP_ACTS.items() if n not in NEW} | {s.prop for s, _a in props.SPELL_ACTS.values()}
    assert len(set(mine)) == len(mine) and not set(mine) & old


def test_the_catalogue_says_built_on_both_sides_with_real_pointers_and_day_weights() -> None:
    for name, (_prop, cid, key) in NEW.items():
        e = BY_ID[cid]
        assert e["desk"]["s"] == "built" and e["app"]["s"] == "built", cid
        assert e["desk"]["names"] == [f"acts:{name}"] and e["app"]["names"] == [f"acts:{key}"], cid
        path, needle = e["desk"]["at"].split("#", 1)
        assert needle in (ROOT / path).read_text(encoding="utf-8"), cid
        assert e["app"]["at"] == f"frontend/js/avatars.js#  {key}: {{ ms:" and f"\n    {key}: {{ ms:" in AV, cid
        assert set(e["day"]) == set(HOURS), cid


@pytest.mark.parametrize("name", sorted(NEW))
def test_the_desk_follows_the_catalogue_day(name: str) -> None:
    e = BY_ID[NEW[name][1]]
    for phase, hour in HOURS.items():
        want = e["mood"].get("content", 1.0) * e["energy"][DOC["energy_by_phase"][phase]] * e["day"][phase]
        assert bh.catalogue_factor(name, "content", hour) == pytest.approx(want), (name, phase)


def test_the_hours_read_as_meant() -> None:
    f = bh.catalogue_factor
    assert f("stargaze_awake", "curious", 2) > 2 * f("stargaze_awake", "curious", 14)
    assert f("tail_stretch", "sleepy", 8) > f("tail_stretch", "sleepy", 19)
    assert f("paper_plane", "happy", 14) > f("paper_plane", "happy", 2)
    assert f("balance_walk", "proud", 2) == 0, "no tightrope at night"


def test_the_app_reads_the_same_factor() -> None:
    from tests._cat_node import run

    acts = {key: {"ms": 1, "w": 1, "cool": 0, "poses": ["stand"]} for _p, _c, key in NEW.values()}
    got = run(
        "nmb.cat.load(); await new Promise((r) => setTimeout(r, 20));"
        "const out = {}; for (const a of Object.keys(NAME_MARK_BUDDY_ACTS)) { out[a] = {};"
        " for (const p of ['morning','afternoon','evening','night']) out[a][p] = nmb.cat.factor(a, 'content', p); }"
        "console.log(JSON.stringify(out));",
        acts,
    )
    for name, (_p, _cid, key) in NEW.items():
        for phase, hour in HOURS.items():
            assert bh.catalogue_factor(name, "content", hour) == pytest.approx(got[key][phase]), (name, phase)


def _gate() -> str:
    start = CSS.index("/* L178 loops */")
    return CSS[start : CSS.index("\n}\n", start)]


@pytest.mark.parametrize("name", sorted(NEW))
def test_each_has_its_app_act_pose_loop_and_words(name: str) -> None:
    prop, _cid, key = NEW[name]
    m = re.search(rf"\n    {key}: \{{ ms: (\d+), w: [0-9.]+, cool: \d+, poses: \[[^\]]+\], atlas: true, desk: true \}}", AV)
    assert m, key
    assert f'["nmb-act-{key}", "' in AV, "the menu says what it is doing"
    assert re.search(rf"#nm-buddy\.nmb-act-{key} [^{{]*\{{[^}}]*(--atl-lean|transform|rotate)", CSS), "its pose"
    assert f"#nm-buddy.nmb-act-{key} " in _gate(), "its loop, inside the motion gate"
    if prop:
        assert f'"{prop}"' in ATLAS or f"nmp nmp-{prop}" in ATLAS, "the prop is drawn"
        assert re.search(rf"#nm-buddy\.nmb-act-{key} [^{{]*\.nmp-{prop}[^{{]*\{{ opacity: 1; \}}", CSS) or re.search(
            rf"#nm-buddy\.nmb-act-{key} \.atl-figure \.nmp-{prop}", CSS
        ), "and shown by its act"


def test_the_lean_and_the_kneel_are_their_own_silhouettes() -> None:
    lean = re.search(r"#nm-buddy\.nmb-act-leanedge \.nm-atlas \{ --atl-lean: (-?[0-9.]+)deg", CSS)
    assert lean and abs(float(lean.group(1))) >= 8
    assert re.search(r"#nm-buddy\.nmb-act-kneel \.nm-atlas \{[^}]*--atl-head-y: [2-9]", CSS), "the head comes down"


def test_help_names_them() -> None:
    from tessellate.ai import help_topics_more

    text = json.dumps(help_topics_more.__dict__, default=str).lower()
    for word in ("paper plane", "conducting", "sketch", "cloud pillow", "tail chase", "back float"):
        assert word in text, word
