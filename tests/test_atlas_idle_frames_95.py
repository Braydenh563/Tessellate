"""L-ui-modernisation-95: the idle Atlas companion's frames, counted.

A CDP trace of the corner Atlas at idle (1440 by 900, the dashboard) put the
main thread's cost in its frames, not its script: about 27 frames a second at
5.7 ms each (style 1.5, paint 1.2, layerize 1.0), the script under 1 ms a
frame, since each frame re-resolves every running animation of the figure.
The frames came from writers on separate clocks: the companion's pacer (a
50 ms beat, whose every beat asked for a frame to learn it was drawn, a step
or not), the lower body's morph (100 ms) and the frame budget's own rAF
loop. These pin the counts with fakes and a fixed clock: the same motion,
fewer frames.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _block(src: str, start: str) -> str:
    at = src.index(start)
    depth = 0
    for i in range(src.index("{", at), len(src)):
        depth += src[i] == "{"
        depth -= src[i] == "}"
        if depth == 0:
            return src[at : i + 1]
    raise AssertionError(start)


def _node(script: str):
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_a_layer_animation_paced_at_10hz_lets_the_beat_sleep_a_beat() -> None:
    """Held animations inside a layer (`nmbTempo.slow`) step every other beat,
    so they carry a gap of 2: with only those and slow props held, the pacer
    wakes ten times a second, not twenty (the sitting Atlas: two head lags
    and the coil, every wake on the 50 ms beat before)."""
    src = (
        "const NMB_PROP_STEPS = 16, NMB_PROP_GAP_MAX = 4, NMB_TEMPO_MS = 50;\nconst nmbTempo = {};\n"
        + AV[AV.index("nmbTempo.step = (") : AV.index("\n};\n", AV.index("nmbTempo.step = (")) + 4]
        + _block(AV, "function nameMarkBuddyPropGaps(")
        + r"""
const anim = (id, ms) => ({ id, effect: { getTiming: () => ({ duration: ms }) } });
const coil = anim("atl-prop", 3000), lagL = anim("", 2937), lagR = anim("", 2937), limb = anim("nmb-limb", 900);
const slow = new WeakSet([coil, lagL, lagR]);
const gaps = nameMarkBuddyPropGaps([coil, lagL, lagR, limb], slow);
process.stdout.write(JSON.stringify({
  coil: gaps.get(coil), lag: gaps.get(lagL), limb: gaps.get(limb) ?? null,
  stride: nmbTempo.step([coil, lagL, lagR], ["paused", "paused", "paused"], gaps),
  withLimb: nmbTempo.step([coil, lagL, limb], ["paused", "paused", "paused"], gaps),
}));
"""
    )
    assert _node(src) == {"coil": 4, "lag": 2, "limb": None, "stride": 2, "withLimb": 1}


def test_a_beat_that_steps_nothing_asks_for_no_frame() -> None:
    """The pacer's after-frame look (`afterFrames`, one rAF) is asked for only by
    a beat that wrote to an animation: an empty beat asked for a frame of its
    own, and each such frame restyled the figure's running animations."""
    fn = _block(AV, "function nameMarkBuddyTempo(")
    assert "let wrote = 0;" in fn
    for write in ("anim.play();", "anim.pause();", "anim.currentTime = t;"):
        assert write in fn
    assert fn.count("wrote += 1") >= 3
    assert "if (wrote) {" in fn
    assert "if (nmbTempo.anims.length) {\n      nmbTempo.wrote = true;" not in fn
    assert "nmbTempo.gap = nameMarkBuddyPropGaps(nmbTempo.anims, nmbTempo.slow);" in fn


CSS = {f: (ROOT / "frontend" / "css" / f).read_text(encoding="utf-8") for f in ("atlas-lazy.css", "characters-lazy.css")}
INDEPENDENT = {"translate", "rotate", "scale"}


def _svg_rules_with_independent_transforms(css: str) -> list[tuple[str, str]]:
    frames = {m.group(1): m.group(2) for m in re.finditer(r"@keyframes ([\w-]+)\s*\{((?:[^{}]*\{[^}]*\})*)\s*\}", css)}
    found = []
    for m in re.finditer(r"([^{};]*?svg)\s*\{\s*animation(?:-name)?:\s*([^;}]*)", css):
        for part in m.group(2).split(","):
            name = part.split()[0] if part.split() else ""
            if INDEPENDENT & set(re.findall(r"([\w-]+)\s*:", frames.get(name, ""))):
                found.append((m.group(1).strip().splitlines()[-1].strip(), name))
    return found


def test_no_css_loop_turns_an_svg_by_an_independent_transform() -> None:
    """Chromium runs a `translate`, `rotate` or `scale` animation on an SVG
    element (an inline `<svg>` root included) on the main thread
    (kSVGTargetHasIndependentTransformProperty), and one such loop asks for a
    frame every vsync, each restyling all of the full figure's hundred running
    loops. Her wisps' and glints' drift and curl were eight of them: with the
    timers cleared the full figure still drew 30 to 60 frames a second, and
    none once those eight were cancelled. They run on an HTML box round each
    drawing (`.atl-lw-drift`), where every one is on the compositor."""
    for name, css in CSS.items():
        assert _svg_rules_with_independent_transforms(css) == [], name
    probe = "@keyframes k { from { rotate: 0deg; } to { rotate: 1deg; } }\n.a > svg { animation: k 1s; }"
    assert _svg_rules_with_independent_transforms(probe) == [(".a > svg", "k")]


def test_the_wisps_drift_box_holds_each_drawing_and_moves_with_its_loops() -> None:
    atlas = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
    assert 'drift.className = "atl-lw-drift";' in atlas
    lazy = CSS["atlas-lazy.css"]
    for name in ("wisps", "wisps-back", "glint-a", "glint-b"):
        assert f".atl-lw-pose-{name} > .atl-lw-drift {{ animation: atl-lw-drift" in lazy
        assert f".atl-lw-pose-{name} > .atl-lw-drift {{ transform-origin: 31px 55.5px; }}" in lazy
    # Paused wherever the drawing's own loops were: lite, away, carried, off and hidden.
    pause = re.search(r"((?:[^{}]*\.atl-lw-drift,?\s*)+)\{ animation-play-state: paused !important; \}", lazy)
    assert pause and pause.group(1).count(".atl-lw-drift") == 5


# --- L-ui-modernisation-201: the lids' layers, unseen but for a blink -------------------------

MOTION = unwrapped((ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8"))
LIDS_STILL = (
    "#nm-buddy:not(.nmb-act-hide) .nm-atlas.atl-layer-lids:not(.atl-blinking, .atl-blinking-slow),\n"
    "#nm-buddy:not(.nmb-act-hide) .nm-atlas.atl-layer-lids:not(.atl-blinking, .atl-blinking-slow) * { transition: none; }"
)


def test_the_hidden_lids_take_each_new_place_at_once() -> None:
    """The three lid layers sit at opacity 0 but for a blink (and the hide act,
    which shows them), and their `rotate` transition as the head attends ran on
    the main thread at every vsync, unseen: a knockout of it took the pinned
    full figure from 185 to 134 ms/s. Unseen, they snap; blinking, they ease as
    before. No `!important` (test_style_scale's ratchet): the id outranks the
    layer's own `transition: rotate`."""
    assert LIDS_STILL in CSS["characters-lazy.css"]


@needs_node
def test_a_blink_waits_out_the_face_moving_under_it() -> None:
    """Snapped lids are where the face is going, so a blink waits while a
    transition moves the face's eyes and not the lids (`atlasBlink.settling`):
    the remaining ms, plus a frame. One that moves both (a box round the two) or
    neither (an iris, a leg) does not hold it."""
    start = MOTION.index("atlasBlink.settling = (")
    src = (
        "class CSSTransition { constructor(target, end, at, state = 'running') { this.effect = { target, getComputedTiming: () => ({ endTime: end, localTime: at }) }; this.playState = state; } }\n"
        "class CSSAnimation {}\n"
        "const atlasBlink = () => {};\n"
        + MOTION[start : MOTION.index("\n};\n", start) + 4]
        + r"""
const node = (name, kids = []) => ({ name, kids, contains(o) { return o === this || this.kids.some((k) => k.contains(o)); } });
const eye = node("eye"), iris = node("iris");
const head = node("head", [eye, iris]);
const lids = node("lids");
const breathe = node("breathe", [head, lids]);
const box = { anims: [], querySelector: (s) => (s.includes("atl-eye") ? eye : s.includes("lids") ? lids : null), getAnimations() { return this.anims; } };
const out = {};
out.none = atlasBlink.settling(box);
box.anims = [new CSSTransition(head, 240, 100)];
out.head = atlasBlink.settling(box);
box.anims = [new CSSTransition(breathe, 240, 100), new CSSTransition(iris, 180, 0), new CSSTransition(head, 240, 240, "finished")];
out.shared = atlasBlink.settling(box);
box.anims = [Object.assign(new CSSAnimation(), { playState: "running", effect: { target: head } })];
out.loop = atlasBlink.settling(box);
process.stdout.write(JSON.stringify(out));
"""
    )
    assert _node(src) == {"none": 0, "head": 156, "shared": 0, "loop": 0}


LIFE = unwrapped((ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8"))


@needs_node
def test_the_morph_prints_each_point_from_a_table_to_the_same_digit() -> None:
    """The morph's tick printed 6,000 numbers a full draw (69 paths, 8 ms of
    script, 3 of it number to string). A table of the strings for every
    hundredth from -50 to 150 gives the same text (`String(atlasFix(v))`), so
    the paths drawn are the same to the digit; outside it, the old way."""
    start = LIFE.index("atlasRigLower.morph.num = (")
    src = (
        "const atlasFix = (v) => Math.round(v * 100) / 100;\nconst atlasRigLower = { morph: {} };\n"
        + LIFE[start : LIFE.index("\n};\n", start) + 4]
        + r"""
const bad = [];
let n = 0;
for (let v = -60; v < 160; v += 0.0037) { n += 1; if (atlasRigLower.morph.num(v) !== String(atlasFix(v))) bad.push(v); }
for (const v of [-0, -0.004, 0.005, -50, 150, 150.004, 1e6, -1e6, 12.345, -12.345]) { n += 1; if (atlasRigLower.morph.num(v) !== String(atlasFix(v))) bad.push(v); }
process.stdout.write(JSON.stringify({ n, bad: bad.slice(0, 5) }));
"""
    )
    got = _node(src)
    assert got["bad"] == [] and got["n"] > 50000
    draw = LIFE[LIFE.index("atlasRigLower.morph.draw = (") : LIFE.index("atlasRigLower.morph.rest = (")]
    assert "o[i] = num(x + dx);" in draw and "o[i + 1] = num(y + dy);" in draw


def test_a_held_blink_tries_again_no_more_than_three_times() -> None:
    fn = _block(MOTION, "function atlasBlink(")
    assert "const wait = waited < 3 ? atlasBlink.settling(box) : 0;" in fn
    assert "atlasBlink(box, slow, waited + 1)" in fn
