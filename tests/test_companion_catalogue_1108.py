"""The companion catalogue (INBOX 1696 dd, v, kk; the owner: "A LOT more biological animation ... tail, lower body, body
position, transitions, movement, actions, behaviour, facial expressions"; "I want the desktop companion to be just as good
as the in-app one and vice versa"; "shaking it makes it turn upside down or flail and get dizzy").

`frontend/companion-catalogue.json` lists every act, pose, face and interaction of both companions, with what each side has
built. Three ratchets: every row of either side's act tables is catalogued (so a new act cannot skip the other side); a
one-sided entry is on an allow list that may only shrink; a seeded hour over the catalogue's weights shows at least
`MIN_ACTS` distinct acts and holds no pose over `MAX_HOLD` s. Fixed seeds, a fixed start hour, no real clock.
"""
from __future__ import annotations

import json
import random
import re
from functools import lru_cache
from pathlib import Path

from tests._js_scope import unwrapped

import pytest

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "frontend" / "companion-catalogue.json"
KINDS = {"tail_pose", "lower_sway", "body_position", "transition", "idle_act", "reaction", "interaction", "face", "movement"}
PREFIX = {"tail_pose": "tail", "lower_sway": "lower", "body_position": "pos", "transition": "trans", "idle_act": "act",
          "reaction": "react", "interaction": "int", "face": "face", "movement": "move"}
SIDES = ("app", "desk")
APP_FILES = ("avatars.js", "atlas.js", "atlas-life.js", "atlas-micro.js", "companion-menu.js")
MIN_ACTS, MAX_HOLD = 12, 90.0
MIN_TAILS, MIN_LOWERS, MIN_FACES = 4, 4, 6
HOURS, SEEDS = (9, 14, 20, 23), (1, 2, 3)
#: What is built today: the fewest distinct acts in any seeded hour (measured 42 in-app, 32 desk on 2026-11-08), set
#: a tenth under, since a row built or added shifts the seeded draws by an act or two. May only rise, with one
#: stated exception (atlascat D2, 2026-11-08): the app's journal, stars, blanket and plant are minutes long
#: (20 to 480 s each, as on the desk), so building them gives each its share of the hour and fewer distinct acts
#: fit: the app's fewest fell from 42 to 34, and the floor was lowered to 31 once, for that, not for a loss.
BUILT_FLOOR = {"app": 31, "desk": 29}

#: One-sided entries (built on one side only). Build the other side, then delete the id here and lower the cap: these only
#: shrink (W31 E1, E2: dangle, kick_legs, hang_one_hand, cross_legged and edge_dangle have desk frames, 27 to 22; L-ui-modernisation-10: sloth and hang_by_feet, 22 to 20; L-ui-modernisation-41: chair, lean and back_float, 20 to 17). The design backlog (built on neither side) is capped too; its build order is
#: `docs/roadmap/agent-remaining/atlascat-1108.md`.
APP_ONLY = frozenset({
    "lower.drift",
    "move.afield", "pos.lounge",
    "trans.back_float>upright",
    "trans.cross_legged>sit", "trans.curl>sit", "trans.edge_dangle>sit", "trans.lounge>sit", "trans.sit>cross_legged",
    "trans.sit>curl", "trans.sit>edge_dangle", "trans.sit>lounge", "trans.sit>upright", "trans.upright>back_float",
    "trans.upright>curl", "trans.upright>lie", "trans.upright>sit",
})
#: What is left has no browser meaning (INBOX 1710): a page is never told its window opened, closed or was dragged.
DESK_ONLY = frozenset({"react.window_closed", "react.window_dragged", "react.window_opened"})
APP_ONLY_CAP, DESK_ONLY_CAP, NEITHER_CAP = 17, 3, 80


@lru_cache(maxsize=1)
def doc() -> dict:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


def entries() -> list[dict]:
    return doc()["entries"]


@lru_cache(maxsize=1)
def by_id() -> dict[str, dict]:
    return {e["id"]: e for e in entries()}


def built(e: dict, side: str) -> bool:
    return e[side]["s"] == "built"


def test_entries_are_well_formed():
    ids = [e["id"] for e in entries()]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for e in entries():
        assert e["kind"] in KINDS and e["id"].startswith(PREFIX[e["kind"]] + "."), e["id"]
        lo, hi = e["seconds"]
        assert 0 < lo <= hi, e["id"]
        for s in SIDES:
            assert e[s]["s"] in {"built", "missing"}, (e["id"], s)
            assert ("at" in e[s]) == built(e, s), (e["id"], s)


def test_built_claims_point_at_real_code():
    """`at` is `path#text`: the text must be in that file, so a claim of built is checked, not trusted."""
    for e in entries():
        for s in SIDES:
            if built(e, s):
                path, _, needle = e[s]["at"].partition("#")
                text = unwrapped((ROOT / path).read_text(encoding="utf-8"))
                assert needle and needle in text, f"{e['id']} {s}: {needle!r} not in {path}"


def _block(text: str, name: str) -> str:
    m = re.search(r"const " + name + r" = \{(.*?)\n\};", text, re.S)
    assert m, name
    return m.group(1)


@lru_cache(maxsize=1)
def app_rows() -> frozenset[str]:
    """Every row of the in-app tables, as `table:key`."""
    text = "".join(unwrapped((ROOT / "frontend" / "js" / f).read_text(encoding="utf-8")) for f in APP_FILES)
    rows = {f"acts:{k}" for k in re.findall(r"^  ([a-z]+): \{ ms: \d+, w: ", text, re.M)}
    for table, name in (("tail", "ATLAS_TAIL_ACTS"), ("mood", "ATLAS_MOODS"), ("lower", "ATLAS_LOWER_STATES"), ("react", "NMB_REACTIONS")):
        rows |= {f"{table}:{k}" for k in re.findall(r"^  ([a-z0-9_]+):", _block(text, name), re.M)}
    #: Rows a lazy file adds to the reactions (companion-menu.js, INBOX 1719 b): `Object.assign(NMB_REACTIONS, {...});`.
    for extra in re.findall(r"^Object\.assign\(NMB_REACTIONS, \{(.*?)\n\}\);", text, re.S | re.M):
        rows |= {f"react:{k}" for k in re.findall(r"^  ([a-z0-9_]+):", extra, re.M)}
    rows |= {f"micro:{k}" for k in re.findall(r"\b([a-z]+):", _block(text, "ATLAS_MICRO_BASE"))}
    pool = re.search(r"NMB_POKE_POOL = \[(.*?)\]", text)
    assert pool
    rows |= {f"poke:{k}" for k in re.findall(r'"([a-z]+)"', pool.group(1))}
    return frozenset(rows)


@lru_cache(maxsize=1)
def desk_rows() -> frozenset[str]:
    """Every row of the desk tables, as `table:key`."""
    from tessellate.core.overlay import behaviour as bh, extras, faces, presence

    extras.register()
    rows = {f"acts:{k}" for k in bh.ACTIVITIES} | {f"react:{k}" for k in extras.REACTIONS} | {f"face:{k}" for k in faces.EXPRESSIONS}
    rows |= {f"spell:{k}" for k in presence.SPELLS} | {f"flow:{p[0]}" for p in bh.FLOW_POSE}
    return frozenset(rows)


@pytest.mark.parametrize("side", SIDES)
def test_every_table_row_is_catalogued(side):
    """A row added to either side's tables needs its entry here, which states the other side's status (INBOX 1696 v)."""
    rows = app_rows() if side == "app" else desk_rows()
    named = {n for e in entries() if built(e, side) for n in e[side]["names"]}
    assert len(rows) > 50, len(rows)
    assert sorted(rows - named) == [], f"{side} rows with no catalogue entry"
    assert sorted(named - rows) == [], f"{side} names that are no longer a table row"


def test_one_sided_entries_are_on_the_allow_lists():
    """Parity (INBOX 1696 v, kk): what one side has, the other is to build. The lists may only shrink."""
    app_only = {e["id"] for e in entries() if built(e, "app") and not built(e, "desk")}
    desk_only = {e["id"] for e in entries() if built(e, "desk") and not built(e, "app")}
    neither = [e["id"] for e in entries() if not built(e, "app") and not built(e, "desk")]
    assert sorted(app_only - APP_ONLY) == [], "new in-app-only entries: build the desk side too"
    assert sorted(desk_only - DESK_ONLY) == [], "new desk-only entries: build the in-app side too"
    assert sorted(APP_ONLY - app_only) == [], "built on both now (or gone): delete these ids and lower the cap"
    assert sorted(DESK_ONLY - desk_only) == [], "built on both now (or gone): delete these ids and lower the cap"
    assert len(APP_ONLY) <= APP_ONLY_CAP and len(DESK_ONLY) <= DESK_ONLY_CAP
    assert len(neither) <= NEITHER_CAP


def test_transitions_cover_every_pair():
    """Between every two core positions a seen in-between (INBOX 1696 dd); the others go by their `via` position."""
    d, ids = doc(), by_id()
    positions = {e["id"][4:] for e in entries() if e["kind"] == "body_position"}
    core = d["core_positions"]
    want = {f"trans.{a}>{c}" for a in core for c in core if a != c}
    for x, via in d["via"].items():
        assert via in core, x
        want |= {f"trans.{via}>{x}", f"trans.{x}>{via}"}
    assert set(core) | set(d["via"]) == positions, "a position with no transitions"
    have = {e["id"] for e in entries() if e["kind"] == "transition"}
    assert sorted(want - have) == [] and sorted(have - want) == []
    for t in have:
        a, _, c = t[6:].partition(">")
        assert (ids[t]["from"], ids[t]["to"]) == (a, c), t


def test_idle_acts_name_real_parts():
    ids = by_id()
    want = {"tail": "tail_pose", "lower": "lower_sway", "face": "face"}
    for e in entries():
        if e["kind"] != "idle_act":
            continue
        assert ids.get(f"pos.{e['pose']}", {}).get("kind") == "body_position", e["id"]
        for field, kind in want.items():
            assert e[field], (e["id"], field)
            for ref in e[field]:
                assert ids.get(ref, {}).get("kind") == kind, (e["id"], ref)
        assert set(e["mood"]) <= set(doc()["moods"]), e["id"]
        assert len(e["energy"]) == 3 and set(e.get("day", {})) <= set(doc()["phases"]), e["id"]


def test_long_acts_change_pose_within_the_budget():
    """No pose held over its position's budget (never over `MAX_HOLD`): a long act has beats, one of them a shift."""
    ids = by_id()
    for e in entries():
        if e["kind"] != "idle_act":
            continue
        budget = min(MAX_HOLD, ids[f"pos.{e['pose']}"]["hold"])
        beats = e.get("beats", [])
        assert all(b["every"][1] <= MAX_HOLD for b in beats), e["id"]
        if e["seconds"][1] > budget:
            assert any(b.get("shifts") and b["every"][1] <= budget for b in beats), f"{e['id']} holds {e['pose']} past {budget} s"


def _phase(hour: float) -> str:
    h = int(hour) % 24
    for name, (a, b) in doc()["phases"].items():
        if (a <= h < b) if a < b else (h >= a or h < b):
            return name
    raise AssertionError(h)


def _weighted(rng: random.Random, pairs: list[tuple[str, float]]) -> str:
    roll = rng.random() * sum(w for _, w in pairs)
    for name, w in pairs:
        roll -= w
        if roll < 0:
            return name
    return pairs[-1][0]


def seeded_hour(seed: int, hour: int, side: str | None = None) -> dict:
    """One hour of idle choices over the catalogue's weights from `hour`:00 (a fixed clock: `t` counts from 0). The mood
    changes every 6 to 12 minutes by the part of the day; energy is the part of the day's, moved by the mood. With
    `side`, only what that side has built. The acts, tail poses, lower sways and faces shown, and the longest hold."""
    d, ids, rng = doc(), by_id(), random.Random(seed)
    parts_rng = random.Random(seed * 7919 + 1)  # its own stream: building a part row must not reshuffle the acts drawn
    acts = [e for e in entries() if e["kind"] == "idle_act" and e.get("w", 0) > 0 and (side is None or built(e, side))]
    parts = {e["id"] for e in entries() if side is None or built(e, side)}
    t, mood, mood_until, recent, last_end = 0.0, "content", 0.0, [], {}
    seen: dict[str, set] = {"acts": set(), "tail": set(), "lower": set(), "face": set()}
    longest = 0.0
    while t < 3600.0:
        phase = _phase(hour + t / 3600.0)
        if t >= mood_until:
            mood = _weighted(rng, list(d["mood_by_phase"][phase].items()))
            mood_until = t + rng.uniform(360.0, 720.0)
        energy = d["energy_by_phase"][phase]
        energy = 0 if mood == "sleepy" else min(2, energy + 1) if mood in ("happy", "startled") else energy
        pairs = []
        for e in acts:
            if e["id"] in recent or t - last_end.get(e["id"], -1e9) < e.get("cool", 0):
                continue
            w = e["w"] * e["mood"].get(mood, 1.0) * e["energy"][energy] * e.get("day", {}).get(phase, 1.0)
            if w > 0:
                pairs.append((e["id"], w))
        e = ids[_weighted(rng, pairs)]
        length = rng.uniform(*e["seconds"])
        longest = max(longest, min([length] + [b["every"][1] for b in e.get("beats", [])]))
        seen["acts"].add(e["id"])
        for field in ("tail", "lower", "face"):
            live = [r for r in e[field] if r in parts]
            if live:
                seen[field].add(parts_rng.choice(live))
        recent = (recent + [e["id"]])[-3:]
        t += length + 1.0
        last_end[e["id"]] = t
    return {**{k: sorted(v) for k, v in seen.items()}, "longest": longest}


@pytest.mark.parametrize("hour", HOURS)
@pytest.mark.parametrize("seed", SEEDS)
def test_a_seeded_hour_is_varied(seed, hour):
    """The catalogue's design (INBOX 1696 dd): at least `MIN_ACTS` distinct acts an hour, no pose over `MAX_HOLD` s."""
    h = seeded_hour(seed, hour)
    assert len(h["acts"]) >= MIN_ACTS, h["acts"]
    assert h["longest"] <= MAX_HOLD, h["longest"]
    assert len(h["tail"]) >= MIN_TAILS and len(h["lower"]) >= MIN_LOWERS and len(h["face"]) >= MIN_FACES, h


@pytest.mark.parametrize("side", SIDES)
def test_built_variety_only_rises(side):
    """What each side shows today in a seeded hour: the floor rises as rows are built, never falls."""
    floor = min(len(seeded_hour(seed, hour, side)["acts"]) for seed in SEEDS for hour in HOURS)
    assert floor >= BUILT_FLOOR[side], floor
