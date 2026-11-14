"""Atlas look, rig and drawing ledger rows (agent atlas-draw)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_atlasrest1402_setup_uses_prefs_not_removed_selects():
    """L749: the moods sweep read #atlas-look, a select that no longer exists, and died on null."""
    src = (ROOT / "scratchpad/ui-sweeps/atlasrest1402.js").read_text()
    assert "getElementById('atlas-look')" not in src
    assert "getElementById('avatar-buddy')" not in src
    assert "prefs.set('atlas-look', look)" in src


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
MOTION = (ROOT / "frontend/js/atlas-motion.js").read_text(encoding="utf-8")


def _node(src: str):
    run = subprocess.run(["node", "-e", src], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    return json.loads(run.stdout)


@needs_node
def test_walk_swing_range_and_counter_phase_l82():
    """L82: measured on a held walk, the raise ranged 4.6 to 21.4 of hanging (17 degrees)."""
    fn = re.search(r"^atlasRigFrame\.walkSwing = function .*?^\};", MOTION, re.S | re.M).group(0)
    out = _node("function atlasRigFrame() {}\n" + fn + r"""
const walkSwing = (...a) => atlasRigFrame.walkSwing(...a);
const r = {};
for (const look of ["masculine", "feminine"]) {
  let sh = [0, 0], el = [0, 0], opp = 0;
  for (let t = 0; t < 4000; t += 10) {
    const a = walkSwing("r", look, t), b = walkSwing("l", look, t);
    sh = [Math.min(sh[0], a[0]), Math.max(sh[1], a[0])];
    el = [Math.min(el[0], a[1], b[1]), Math.max(el[1], a[1], b[1])];
    opp = Math.max(opp, Math.abs(a[0] + b[0]));
  }
  r[look] = { sh, el, opp };
}
console.log(JSON.stringify(r));""")
    assert out["masculine"]["sh"][1] <= 9.001 and out["masculine"]["sh"][0] >= -9.001
    assert out["feminine"]["sh"][1] <= 6.001 and out["feminine"]["sh"][0] >= -6.001
    assert out["masculine"]["sh"][1] > 8.9, "the swing reaches its amplitude"
    for look in out.values():
        assert look["opp"] < 1e-9, "the arms swing half a stride apart"
        assert look["el"][0] >= 0, "the elbow never straightens past hanging while walking"
    assert out["masculine"]["el"][1] <= 5.5


CSS = (ROOT / "frontend/css/08-consistency.css").read_text(encoding="utf-8")
AVATARS = (ROOT / "frontend/js/avatars.js").read_text(encoding="utf-8")
#: The Atlas rig's cap is 200 degrees a second at its fastest (`ATLAS_RIG_MAX_SPEED`); an ease-in-out
#: curve's fastest moment is 1.55 times its mean over a segment, so a generic face's arm keyframes
#: stay under 200 / 1.55 = 129 a second between frames (5 percent slack for the rounded offsets).
ARM_MEAN_CAP = 200 / 1.55 * 1.05


def _keyframe_speeds(name: str, seconds: float, rest: float = 0.0) -> list[tuple[float, float]]:
    """(offset, degrees) frames of a rotate keyframes block, from and back to `rest`; returns mean deg/s per segment."""
    body = re.search(r"@keyframes " + re.escape(name) + r" \{(.*?)\n\}", CSS, re.S).group(1)
    frames: dict[float, float] = {}
    for sel, val in re.findall(r"([\d%,\s]+)\{\s*transform: rotate\((-?\d+(?:\.\d+)?)deg\)", body):
        for off in re.findall(r"(\d+(?:\.\d+)?)%", sel):
            frames[float(off) / 100] = float(val)
    pts = [(0.0, rest)] + sorted(frames.items()) + [(1.0, rest)]
    return [(abs(b[1] - a[1]) / ((b[0] - a[0]) * seconds), b[0] - a[0]) for a, b in zip(pts, pts[1:]) if b[0] > a[0]]


def _arm_animations() -> list[tuple[str, float]]:
    """Every generic-face arm animation: (keyframes name, seconds), from the rules that set one on an arm."""
    found = []
    for m in re.finditer(r"^\s*(&[^{]*\.nmb-arm-[lr])\s*\{\s*animation:\s*([\w-]+)\s+(\d+(?:\.\d+)?)s", CSS, re.M):
        sel, name, secs = m.groups()
        if ".atl-figure" in sel or name.startswith(("atl-", "nmv-")):
            continue
        found.append((name, float(secs)))
    return found


def test_generic_arm_keyframes_obey_the_rig_speed_cap_l83():
    """L83: the wave swung 98 degrees in 240 ms (408 a second mean, 3x the Atlas rig's cap); hide 352; scratch 385."""
    anims = _arm_animations()
    names = {n for n, _ in anims}
    assert {"nmb-wave", "nmb-wave-l", "nmb-hide-l", "nmb-hide-r", "nmb-scratch"} <= names, names
    for name, secs in anims:
        worst = max(v for v, _ in _keyframe_speeds(name, secs))
        assert worst <= ARM_MEAN_CAP, f"{name} over {secs}s turns {worst:.0f} degrees a second (cap {ARM_MEAN_CAP:.0f})"


def test_viewer_wave_obeys_the_cap_l83():
    """The large view's wave (nameMarkIdleAct) is a Web Animation: lift 120 degrees, swing, return."""
    m = re.search(r'act === "wave"\) \{\s*part\("\.nmb-arm-r"\)\?\.animate\(\[(.*?)\], \{ duration: (\d+)', AVATARS, re.S)
    frames = re.findall(r'\{ rotate: "(-?\d+)deg"(?:, offset: ([\d.]+))? \}', m.group(1))
    assert frames
    secs = int(m.group(2)) / 1000
    pts = [(float(o) if o else (0.0 if i == 0 else 1.0), float(d)) for i, (d, o) in enumerate(frames)]
    worst = max(abs(b[1] - a[1]) / ((b[0] - a[0]) * secs) for a, b in zip(pts, pts[1:]))
    assert worst <= ARM_MEAN_CAP, f"viewer wave turns {worst:.0f} a second"


@needs_node
def test_limb_gesture_arm_frames_obey_the_cap_l83():
    """Leap, glide, float and cue arm frames, at the durations the callers pass, are clamped to the cap."""
    fn = re.search(r"^  function nmbArmKeys\(.*?^  \}", AVATARS, re.S | re.M)
    assert fn, "nmbArmKeys is the clamp"
    out = _node("const NMB_ARM_MEAN_SPEED = %s;\n%s\nconsole.log(JSON.stringify(nmbArmKeys([[0.14, -16], [0.5, 52], [0.84, 16]], 700)))" % (
        re.search(r"const NMB_ARM_MEAN_SPEED = ([\d.]+);", AVATARS).group(1), fn.group(0)))
    pts = [(0.0, 0.0)] + [tuple(p) for p in out] + [(1.0, 0.0)]
    for a, b in zip(pts, pts[1:]):
        assert abs(b[1] - a[1]) / ((b[0] - a[0]) * 0.7) <= ARM_MEAN_CAP + 0.01, (a, b)
    assert max(abs(d) for _, d in out) >= 10, "it still moves"


REVEAL = (ROOT / "frontend/js/reveal-targets.js").read_text(encoding="utf-8")


@needs_node
def test_reveal_scrolls_a_control_clipped_above_its_scroller_l85():
    """L85: a Settings control at 148 with its scroller's top at 174 (390 wide) counted as in view and never scrolled."""
    fn = re.search(r"^function flashRevealed\(.*?^\}", REVEAL, re.S | re.M).group(0)
    out = _node(
        r"""
const calls = [];
const doc = { documentElement: {}, body: {} };
globalThis.document = doc; globalThis.window = { innerHeight: 844, innerWidth: 390 };
const revealTimers = new Map();
const reducedMotionWanted = () => true;
const scroller = { getBoundingClientRect: () => ({ top: 174, bottom: 806 }) };
function nearestScrollParent() { return scroller; }
const make = (top) => {
  const el = { classList: { remove() {}, add() {} }, offsetWidth: 1, parentElement: null,
    closest: () => null, matches: () => false,
    getBoundingClientRect: () => ({ top, bottom: top + 40, left: 10, right: 300 }),
    scrollIntoView: (o) => calls.push([top, o.block]) };
  return el;
};
""" + fn + r"""
for (const top of [148, 300, 790]) flashRevealed(make(top));
console.log(JSON.stringify(calls));""")
    assert [c[0] for c in out] == [148, 790], "clipped above and below the scroller are brought into view; 300 is left alone"


def test_atlas_lids_hide_runs_with_the_arms_l175():
    """L175: the lids shut over 2.4s (18% to 82%) while the arms took 3.6s (33% to 67%), so the eyes were shut
    before the hands came up and open again before they came down."""
    css = (ROOT / "frontend/css/08-consistency.css").read_text(encoding="utf-8")
    arms = re.search(r"\.nmb-arm-l \{ animation: nmb-hide-l ([\d.]+)s", css).group(1)
    lids = re.search(r"\.atl-layer-lids \{ animation: atl-lids-hide ([\d.]+)s", css).group(1)
    assert lids == arms == "3.6"
    arm_keys = re.search(r"@keyframes nmb-hide-l \{\s*([\d%, ]+) \{", css).group(1)
    lid_keys = re.search(r"@keyframes atl-lids-hide \{.*?\n\s*([\d%, ]+) \{ opacity: 1", css, re.S).group(1)
    assert arm_keys.replace(" ", "") == lid_keys.replace(" ", "") == "33%,67%"


def test_every_endless_atlas_loop_holds_at_rest_l742():
    """L742 (owner: motion still pauses at rest): `.atl-lw-wisps`, `-wisps-back` and the two glints loop
    forever (atl-wisp-drift) but were missing from the is-calm hold, so her wisps drifted on at rest."""
    css = (ROOT / "frontend/css/08-consistency.css").read_text(encoding="utf-8")
    hold = re.search(r":root\.is-calm :is\((.*?)\) \{ animation-play-state: paused !important; \}", css, re.S).group(1)
    looped = set(re.findall(r"& :is\(([^)]*)\) \{ animation: atl-wisp-drift", css)[0].replace(" ", "").split(","))
    looped |= {".atl-lw-wisps"}
    for sel in looped:
        assert sel in hold.replace(" ", ""), f"{sel} loops endlessly and is not held at rest"


def test_animal_only_acts_stay_off_atlas_l746():
    """L746: the table (WORLD_CLASS_PLAN.md) names groom, sniff and shake as the generated faces' own (a coat and
    a nose); the picker, the mind's next act and the viewer's chips all read `generated` as they read `atlas`."""
    avatars = (ROOT / "frontend/js/avatars.js").read_text(encoding="utf-8")
    menu = (ROOT / "frontend/js/companion-menu.js").read_text(encoding="utf-8")
    for act in ("shake", "groom", "sniff"):
        assert re.search(rf"^\s+{act}: \{{[^}}\n]*generated: true", avatars, re.M), act
    assert "if (spec.generated && nmb.atlasLook) w = 0;" in avatars
    assert "if (spec.generated && nmb.atlasLook) return \"\";" in menu
    assert "(spec.generated && atlas)" in menu


@needs_node
def test_hide_act_draws_its_hands_on_the_front_layer_l175():
    """L175: measured in the browser, 130 pixels of the 64 by 92 figure differ with the front copies hidden, and
    the copies are gone (0) once the act ends. The rig drives a copy with its original."""
    assert 'atlasRigFrame.hideHands(rig, !!buddy && buddy.classList.contains("nmb-act-hide"));' in MOTION
    fn = re.search(r"^atlasRigFrame\.hideHands = function .*?^\};", MOTION, re.S | re.M).group(0)
    out = _node("function atlasRigFrame() {}\n" + fn + r"""
const mk = () => { const o = { isConnected: true, children: [], remove() { this.isConnected = false; }, cloneNode() { return mk(); },
  querySelectorAll() { return []; }, querySelector() { return null; } }; return o; };
const host = mk(); host.appendChild = (c) => host.children.push(c);
const arm = { groups: [mk(), mk()], paths: [], cloneHands: [], shown: "x", drawn: [0, 0] };
const rig = { box: { querySelector: () => host }, arms: [arm], hideCopies: null };
atlasRigFrame.hideHands(rig, true);
const on = { groups: arm.groups.length, copies: rig.hideCopies.length, shown: arm.shown };
atlasRigFrame.hideHands(rig, true);
const again = host.children.length;
atlasRigFrame.hideHands(rig, false);
console.log(JSON.stringify({ on, again, off: { groups: arm.groups.length, copies: rig.hideCopies } }));""")
    assert out["on"] == {"groups": 4, "copies": 2, "shown": ""}
    assert out["again"] == 2, "a second call adds nothing"
    assert out["off"] == {"groups": 2, "copies": None}


@needs_node
def test_lower_body_weave_adds_texture_to_both_looks_l742():
    """L742: the dress and the trail each carry the same 18 fine specks on top of their dust (a speck's radius
    0.07 to 0.11, inside the stem's width), and both looks read it."""
    atlas = (ROOT / "frontend/js/atlas.js").read_text(encoding="utf-8")
    assert atlas.count("...atlasSpecks.weave()") == 2
    line = re.search(r"^atlasSpecks\.weave = .*;$", atlas, re.M).group(0)
    out = _node("const atlasSpecks = () => 0;\n" + line + "\nconsole.log(JSON.stringify(atlasSpecks.weave()))")
    assert len(out) == 18
    assert all(0.27 <= t <= 0.92 and abs(a) <= 0.35 and 0.069 <= r <= 0.111 for t, a, r in out)
    assert len({round(a, 2) for _, a, _ in out}) >= 14, "the rows never line up"


def test_companionperf_sets_the_buddy_through_prefs_not_the_removed_select():
    """The sweep read #avatar-buddy, a select that no longer exists, and died on null (the same break as L749)."""
    src = (ROOT / "scratchpad/ui-sweeps/companionperf.js").read_text()
    assert "getElementById('avatar-buddy')" not in src
    assert src.count("prefs.set('avatar-buddy', k); syncNameMarkBuddy();") == 2


def test_desk_renderer_captures_every_frame_at_full_size_l150():
    """The renderer could not finish (no `tumble` capture, though its handler stayed) and shot about half its takes
    with the app's fit scale at 0.75 (a 48 by 69 figure box for 64 by 92), which seamed the idle cycle."""
    js = (ROOT / "scripts/render_desk_frames.js").read_text(encoding="utf-8")
    assert 'name: "tumble"' in js and "spin: 115" in js
    assert '#nm-buddy .nm-buddy-face { scale: 1 !important; transition: none !important; }' in js
    life = (ROOT / "frontend/js/atlas-life.js").read_text(encoding="utf-8")
    assert "atlasTailFrame.kit = {" in life and "if (atlasTailFrame.kit.hold === tail) return;" in life
