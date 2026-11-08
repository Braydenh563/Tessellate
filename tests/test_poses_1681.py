"""INBOX 1681 (the owner: "think of more positions ... sitting or crouching
down, lying down, floating, walking, gliding, lounging, climbing, hanging,
resting etc. all small things and more").

Every new pose is an act of the existing decide machinery (no new timer or
frame loop), picked in the poses it suits, with three drawn variants chosen
by `nameMarkBuddyPickVariant` (`data-variant`), a lower body of its own for
Atlas that turns at most 4 degrees off the torso (INBOX 615 and 619), and
loops only behind the motion gates (a still figure with reduced motion: the
tick makes no act at all). The 1680 sway is two incommensurate periods.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
LIFE = (ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8")
MOTION = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
TRAVEL = (ROOT / "frontend" / "css" / "companion-travel-lazy.css").read_text(encoding="utf-8")
ATLAS_CSS = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

#: act -> (poses it is picked in, the Atlas lower state it takes)
POSES = {
    "crouch": (["stand"], "crouch"),
    "lounge": (["sit"], "lounge"),
    "rest": (["sit", "stand", "lean"], None),
    "glide": (["float"], "glide"),
    "drift": (["float"], "drift"),
    "climb": (["hang"], "hang"),
}


def _node(script: str) -> str:
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr[-600:]
    return done.stdout


def _block(src: str, start: str, end: str) -> str:
    return src[src.index(start) : src.index(end, src.index(start))]


def _fn(name: str, src: str = AV) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def test_every_pose_is_an_act_with_three_variants_and_a_switch() -> None:
    acts = _block(AV, "Object.assign(NAME_MARK_BUDDY_ACTS, {\n  crouch", "});")
    variants = re.search(r"const NMB_VARIANTS = \{([^}]*)\}", AV).group(1)
    activities = _block(AV, "const NMB_ACTIVITIES = [", "];")
    for act, (poses, _) in POSES.items():
        row = re.search(rf"  {act}: \{{ ms: ([0-9]+), w: ([0-9.]+), cool: ([0-9]+), poses: \[([^\]]*)\]", acts)
        assert row, act
        assert float(row.group(2)) > 0 and int(row.group(3)) >= 40000, (act, "picked, and not twice a minute")
        assert re.findall(r'"(\w+)"', row.group(4)) == poses, act
        assert "lazy: true" in acts[acts.index(f"  {act}:") :].split("\n", 1)[0], act
        assert re.search(rf"\b{act}: 3\b", variants), (act, "three variants")
        assert f'"{act}"' in activities, (act, "a switch in What it does")
    # The lie-down grew a third (a knee up) and the sway is not one sinusoid.
    assert re.search(r"\blie: 3\b", variants)


def test_every_variant_is_drawn_for_plain_companions_and_atlas_alike() -> None:
    for act in POSES:
        for n in range(3):
            assert f'.nmb-act-{act}[data-variant="{n}"]' in TRAVEL, (act, n)
    for n in (1, 2):
        assert f'#nm-buddy.nmb-act-lie[data-variant="{n}"][data-pose] .nmb-leg-' in TRAVEL, n
    # A specificity bump over the pose rules, written once and named.
    assert "[data-pose]" in TRAVEL
    # Distinct pictures: no two variants of an act share a body rule.
    for act in POSES:
        bodies = re.findall(rf'#nm-buddy\.nmb-act-{act}\[data-variant="([0-9])"\]\[data-pose\] \.nm-buddy-char \{{ ([^}}]*) \}}', TRAVEL)
        assert len(bodies) >= 3 and len({b for _, b in bodies}) == len(bodies), (act, bodies)


def test_loops_sit_behind_the_motion_gates_and_poses_are_compositor_only() -> None:
    section = _block(TRAVEL, "/* Poses 1681 */", "/* End poses 1681 */")
    before, _, gated = section.partition("@media all {")
    assert "animation" not in before, "a still figure keeps still poses only"
    assert ':root:not([data-avatar-motion="off"])' in gated
    for prop in re.findall(r"^\s*(?:[#&.:\[][^{]*)\{ ?([a-z-]+):", section, re.M):
        assert prop in {"transform", "rotate", "translate", "scale", "animation", "animation-delay", "opacity", "transition"} or prop.startswith("--atl-"), prop
    assert not re.search(r"\b(width|height|top|left|margin|padding)\s*:", section)
    # Reduced motion: the tick returns before it decides, so no act starts.
    tick = _fn("nameMarkBuddyTick")
    assert tick.index("if (nameMarkBuddyStill()) {") < tick.index("nameMarkBuddyDecide()")


def test_the_atlas_lower_body_has_a_pose_for_each_and_holds_the_join() -> None:
    table = _block(LIFE, "const ATLAS_LOWER_STATES = {", "const ATLAS_HAIR_STATES")
    hair = LIFE[LIFE.index("const ATLAS_HAIR_STATES") : LIFE.index("const ATLAS_NEB_STATES")]
    neb = LIFE[LIFE.index("const ATLAS_NEB_STATES") : LIFE.index("function atlasRigLowerAttach(")]
    for state in sorted({s for _, s in POSES.values() if s}):
        row = re.search(rf'  {state}: \{{ ms: ([0-9]+), ease: "([^"]+)", v: (\[\[.*\]\]) \}},', table)
        assert row, state
        variants = re.findall(r"\[(-?[0-9.]+), ([0-9.]+), ([0-9.]+), (-?[0-9.]+), (-?[0-9.]+)\]", row.group(3))
        assert len(variants) >= 3 and len(set(variants)) == len(variants), state
        assert max(abs(float(v[0])) for v in variants) <= 4, (state, "the join cap")
        assert re.search(rf"\b{state}: \[", hair) and re.search(rf"\b{state}: \[\[", neb), state
    # An act state takes the act's drawn variant, so the body and the lower body agree.
    assert "atlasRigLower.acts" in LIFE and "Number(buddy?.dataset.variant)" in LIFE


@needs_node
def test_the_lower_state_follows_the_act_class_and_the_hang() -> None:
    src = _fn("atlasLowerState", MOTION) + re.search(r"^atlasLowerState\.acts = .*;$", MOTION, re.M).group(0)
    script = (
        src
        + """
const make = (classes, pose = "", travel = "") => ({ classList: { contains: (c) => classes.includes(c) }, dataset: { pose, travel } });
const box = { dataset: {} };
console.log(JSON.stringify([
  atlasLowerState(make(["nmb-act-crouch"], "stand"), box),
  atlasLowerState(make(["nmb-act-lounge"], "sit"), box),
  atlasLowerState(make(["nmb-act-glide"], "float"), box),
  atlasLowerState(make(["nmb-act-drift"], "float"), box),
  atlasLowerState(make([], "hang"), box),
  atlasLowerState(make(["nmb-act-climb"], "hang"), box),
  atlasLowerState(make(["nmb-act-lounge", "nmb-sleep"], "sit"), box),
  atlasLowerState(make([], "sit"), box),
  atlasLowerState(make([], "stand"), box),
]));
"""
    )
    out = json.loads(_node(script))
    assert out == ["crouch", "lounge", "glide", "drift", "hang", "hang", "lie", "sit", "idle"]


@needs_node
def test_each_pose_is_reachable_from_the_decide_path_in_its_poses_only() -> None:
    acts = AV[AV.index("const NAME_MARK_BUDDY_ACTS = {") : AV.index("});\n", AV.index("  climb: {", AV.index("  crouch: {"))) + 4]
    quiet = re.search(r"^const NMB_QUIET_ACTS = .*;$", AV, re.M).group(0)
    script = (
        "let seed = 7; Math.random = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);\n"
        "const NAME_MARK_BUDDY_MOODS = {}, NAME_MARK_BUDDY_KINDS = {}, NMB_YAWN_MS = 1e9;\n"
        "globalThis.document = { querySelector: () => ({ dataset: { atlasLook: 'feminine' } }) };\n"
        + acts
        + "\n"
        + quiet
        + "\n"
        + "let off = new Set();\n"
        + "const nameMarkBuddyActivitiesOff = () => off, nameMarkBuddyActOff = (a, o = off) => o.has(a), nameMarkBuddyActions = () => 'normal';\n"
        + "const nameMarkBuddyCalmAllows = () => true, nameMarkBuddyScrollAgo = () => 1e9, nameMarkBuddyWarmthAt = () => 0;\n"
        + "const nameMarkBuddyTraits = () => ({ loud: 1 });\n"
        + "const nmb = { lastInput: 0, reading: {}, cool: {}, recentActs: [], lastAct: '', mood: { energy: 0.5, curiosity: 0.5, sociability: 0.5 }, grumpyUntil: 0, lastCheer: 0, lastPoke: 0, feel: null, pointer: null, visit: false, travelPlay: () => true, legs: '', edgeType: '', onBoard: false, pose: 'stand', mind: null, cat: { weigh: () => 1 } };\n"
        + "const NMB_BOARD_WANDER = 0.35;\n"
        + _fn("nameMarkBuddyDecide")
        + """
const seen = {};
for (const pose of ["stand", "sit", "float", "hang", "lean"]) {
  for (let i = 0; i < 4000; i += 1) {
    nmb.pose = pose; nmb.cool = {}; nmb.recentActs = []; nmb.lastAct = "";
    const act = nameMarkBuddyDecide(1e7, 12);
    (seen[act] ||= new Set()).add(pose);
  }
}
off = new Set(["crouch", "lounge", "rest", "glide", "drift", "climb"]);
let leaked = 0;
for (const pose of ["stand", "sit", "float", "hang", "lean"]) for (let i = 0; i < 800; i += 1) {
  nmb.pose = pose; nmb.cool = {}; nmb.recentActs = [];
  if (off.has(nameMarkBuddyDecide(1e7, 12))) leaked += 1;
}
console.log(JSON.stringify({ seen: Object.fromEntries(Object.entries(seen).map(([k, v]) => [k, [...v].sort()])), leaked }));
"""
    )
    out = json.loads(_node(script))
    for act, (poses, _) in POSES.items():
        assert out["seen"].get(act) == sorted(poses), (act, out["seen"].get(act))
    assert out["leaked"] == 0, "a switched-off pose is never picked"


@needs_node
def test_the_variant_pick_reaches_all_three_and_never_repeats() -> None:
    pick = _fn("nameMarkBuddyPickVariant")
    script = pick + "\nlet seed = 11; const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;\nlet last = -1; const counts = [0, 0, 0]; let repeats = 0;\nfor (let i = 0; i < 3000; i += 1) { const v = nameMarkBuddyPickVariant(3, last, rand()); if (v === last) repeats += 1; counts[v] += 1; last = v; }\nconsole.log(JSON.stringify({ counts, repeats }));"
    out = json.loads(_node(script))
    assert out["repeats"] == 0 and min(out["counts"]) > 900


def test_the_resting_poses_are_paced_as_rest_and_the_big_ones_are_loud() -> None:
    resting = re.search(r"const NMB_RESTING_ACTS = new Set\(\[(.*?)\]\)", AV).group(1)
    for act in ("crouch", "lounge", "rest", "drift"):
        assert f'"{act}"' in resting, act
    loud = re.search(r"^const NMB_LOUD_ACTS = (.*);$", AV, re.M).group(1)
    for act in ("glide", "climb"):
        assert f'"{act}"' in loud, act
    quiet = re.search(r"^const NMB_QUIET_ACTS = (.*);$", AV, re.M).group(1)
    for act in ("lounge", "rest", "drift"):
        assert f'"{act}"' in quiet, act


def test_the_lower_body_sway_is_two_periods_not_one_clean_sinusoid() -> None:
    # The 1680 review: a rigid single sinusoid. The turn and the stretch now
    # run on their own periods per part, so the figure never repeats a pose
    # within a minute, and none of the six periods is shared.
    gated = _block(ATLAS_CSS, "@media all {", ":root[data-atlas-lite] .atl-figure-box .atl-lw-pose,")
    rows = re.findall(r"animation: (atl-lw-sway-\w+) ([0-9.]+)s [^,]*, (atl-lw-bob-\w+) ([0-9.]+)s", gated)
    assert len(rows) == 3, rows
    periods = [float(p) for _, a, _, b in rows for p in (a, b)]
    assert len(set(periods)) == 6, periods
    for name in ("atl-lw-sway-lower", "atl-lw-sway-wisps", "atl-lw-sway-tail"):
        frames = _block(ATLAS_CSS, f"@keyframes {name} {{", "\n@keyframes")
        assert "rotate" in frames and "scale" not in frames, name
    for name in ("atl-lw-bob-lower", "atl-lw-bob-wisps", "atl-lw-bob-tail"):
        frames = ATLAS_CSS[ATLAS_CSS.index(f"@keyframes {name} {{") :].split("}", 2)[0]
        assert "scale" in frames and "rotate" not in frames, name
    # Asleep: both swap, with their own slower periods, under the same gates.
    sleep = ATLAS_CSS[ATLAS_CSS.index("[data-pose^=\"curl\"]) .nm-live {") :]
    assert sleep.count("animation-duration:") >= 3 and "atl-lw-sleep-bob-lower" in sleep
