"""INBOX 687: Atlas breathes where it can be seen.

The owner: "does the companion or at least atlas have a subtle breathing
look??" Sampled at rest for 10 s (`scratchpad/ui-sweeps/breath687.js`), the
layered figure's breath was a 0.45px lift and a 0.6% widening of the whole
upper body: 0.1px on the companion, 0.2px in the large view, the head
widening as much as the torso. The chest now swells a few percent about the
hips while the head, the arms and the face keep their size, written ten
times a second from the tail's loop (atlas-life.js, `atlasBreathFrame`): as a
CSS loop inside the drawing it repainted the large view's body every frame
and took that view from 53 frames a second to 20 to 31.

Intent moved (atlasidle2, 2026-11-07): the ten-a-second write is itself a cost
(each style write restyles every animated element: 90 restyles in 6 s of the
hanging pose). It is now one Web Animation of `transform` per torso, started
on the rise's start time and set again only when the figure's look changes or
it comes back from being still. The shape (a few percent, wider than tall, on
the rise's clock, at rest when still) is what the tests below still hold.

Intent moved again (L138, L231, 2026-11-14): a `transform` animation on an svg
`<g>` is never composited (an invalidation trace showed "Style changed
g.nmb-torso" every frame; 975 of 1,950 recalcs a minute were the torso's
alone), so the swell is written in the lower body's 10 Hz morph task, whose
path writes restyle that frame anyway (`atlasBreathFrame.put`). Seeded A/B,
headless: layouts 2,165-2,189 to 1,169-1,339 a minute, layout ms 1,097-1,741
to 210-253.
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
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
LIFE = unwrapped((ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8"))


def _fn(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", LIFE, re.S | re.M)
    assert match, f"{name} is gone from atlas-life.js"
    return match.group(0)


def _duration(rule_start: str) -> float:
    match = re.search(re.escape(rule_start) + r"[^}]*?(?:animation: [\w-]+ |animation-duration: )([0-9.]+)s", CSS)
    assert match, rule_start
    return float(match.group(1))


def _run(body: str):
    swell = re.search(r"^const ATLAS_BREATH_SWELL = .*;$", LIFE, re.M).group(0)
    put = re.search(r"^atlasBreathFrame\.put = .*?^\};", LIFE, re.M | re.S).group(0)
    script = "let clock = 0;\nconst performance = { now: () => clock };\n" + swell + "\n" + _fn("atlasBreathFrame") + "\n" + put + "\n" + body
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


FAKE = """
const made = (look, rise) => {
  const torsos = [0, 1].map(() => ({ style: { transform: "" }, writes: 0 }));
  for (const t of torsos) { let v = ""; Object.defineProperty(t.style, "transform", { get: () => v, set(x) { v = x; t.writes += 1; } }); }
  return {
    dataset: { atlasLook: look },
    querySelectorAll: () => torsos,
    querySelector: () => (rise ? { getAnimations: () => [rise] } : null),
  };
};
const anim = (ms, start) => ({ playState: "running", startTime: start, currentTime: 0, effect: { getComputedTiming: () => ({ duration: ms }) } });
const swell = (v) => (v.match(/[0-9.]+/g) || ["1", "1"]).map(Number);
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_chest_swells_on_the_rise_clock_and_rests_when_still():
    out = _run(
        FAKE
        + """
const res = { peak: [1, 1], low: [9, 9] };
const box = made("masculine", anim(4600, 0));
atlasBreathFrame(box, true);
for (let t = 0; t <= 4600; t += 100) { clock = t; atlasBreathFrame.put(box, t); const [x, y] = swell(box.atlasTorsos[0].style.transform); if (x > res.peak[0]) res.peak = [x, y]; if (x < res.low[0]) res.low = [x, y]; if (t === 2300) res.half = [x, y]; }
res.same = box.atlasTorsos[0].style.transform === box.atlasTorsos[1].style.transform;
const fem = made("feminine", null);
atlasBreathFrame(fem, true);
res.fem = fem.atlasBreath.period;
const late = made("masculine", anim(4600, -1150));
clock = 0;
atlasBreathFrame(late, true);
res.latePh = late.atlasBreath.ph;
const still = made("masculine", anim(4600, 0));
atlasBreathFrame(still, true);
clock = 1000; atlasBreathFrame.put(still, 1000);
atlasBreathFrame(still, false);
res.still = still.atlasTorsos.map((t) => t.style.transform);
res.cleared = still.atlasBreath === null;
process.stdout.write(JSON.stringify(res));
"""
    )
    assert out["low"] == [1, 1], "starts and ends at rest"
    assert out["peak"] == [1.035, 1.025] and out["half"] == [1.035, 1.025], "the peak is a few percent, wider than tall, at the half"
    assert out["same"], "both torsos (fills and edges) move as one"
    assert out["fem"] == 4000, "her breath is 4 s when no rise is running"
    assert abs(out["latePh"] - 0.25) < 1e-6, "the phase is the rise's: one clock"
    assert out["still"] == ["", ""] and out["cleared"], "still by setting, off screen or hidden: back at rest"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_morph_writes_the_breath_and_the_tail_beat_holds_off():
    out = _run(
        FAKE
        + """
const box = made("masculine", anim(4600, 0));
atlasBreathFrame(box, true);
const first = box.atlasTorsos[0].writes;
// The morph's 10 Hz task writes; the tail's 66 ms beats between them write nothing.
for (let t = 0; t <= 3000; t += 33) { clock = t; if (t % 99 === 0) atlasBreathFrame.put(box, t); atlasBreathFrame(box, true); }
const ridden = box.atlasTorsos[0].writes - first;
// No morph (a figure without a lower rig): the tail's beat writes it.
const bare = made("masculine", anim(4600, 0));
clock = 0;
atlasBreathFrame(bare, true);
for (let t = 500; t <= 3000; t += 400) { clock = t; atlasBreathFrame(bare, true); }
process.stdout.write(JSON.stringify({ ridden, bare: bare.atlasTorsos[0].writes }));
"""
    )
    assert out["ridden"] <= 31, f"{out['ridden']} writes in 3 s: the morph's ticks only"
    assert out["bare"] >= 6, "the tail's beat writes where no morph does"


def test_it_rides_the_tail_loop_which_knows_the_motion_gates():
    frame = _fn("atlasTailFrame")
    # And behind the lock (`data-atlas-hidden`, Brief 34 decision 7).
    assert "const live = atlasMotionOK(box) && !box.classList.contains(\"atl-off\") && !document.hidden && !document.documentElement.hasAttribute(\"data-atlas-hidden\");" in frame
    # Called before the loop skips its odd frames, so a still figure is put
    # back at rest by the one frame the loop draws then.
    assert frame.index("atlasBreathFrame(box, live);") < frame.index("if (live && tail.tick % 2 && tail.drawn && !tail.calm)")


def test_only_the_torso_breathes_and_no_animation_runs_inside_the_drawing():
    body = _fn("atlasBreathFrame")
    assert '".atl-layer-body .nmb-torso"' in body
    # No Web Animation on the svg `<g>`: it never composites and restyles every animated element each frame.
    assert "el.animate(" not in body and ".animate(" not in body
    morph = LIFE[LIFE.index("atlasRigLower.morph.run = ") :]
    assert "atlasBreathFrame.put(box, now);" in morph[: morph.index("m.moved = true;")]
    assert ".atl-layer-body .nmb-torso { transform-origin: 31px 60px; }" in CSS, "about the hips (ATLAS_GEO.hips, y 60)"
    # Nothing in the stylesheet animates the torso: one breath, here.
    assert not re.search(r"nmb-torso[^{]*\{[^}]*animation", CSS)


def test_the_rise_has_a_period_clear_of_the_idle_clocks():
    masc = _duration("& .atl-lw-breathe {")
    fem = _duration('& .atl-lw-body[data-atlas-look="feminine"] .atl-lw-breathe {')
    # The idle clocks a breath could beat against: the sways, the hair, the
    # tail's flow, the nebula, the hem's wind, her float and wisps, the
    # large view's weight shift and bob (avatars.js, 6.7s and 4.3s).
    clocks = {"m": [7.2, 8.3, 7.7, 6.3, 5.4, 5.6, 13, 6.7, 4.3], "f": [9.4, 5.3, 6.8, 7.1, 8.3, 7.7, 5.4, 5.6, 13, 6.7, 4.3]}
    for look, period in (("m", masc), ("f", fem)):
        assert 4 <= period <= 5, (look, period)
        for clock in clocks[look]:
            ratio = max(period, clock) / min(period, clock)
            for simple in (1, 1.5, 2, 2.5, 3):
                assert abs(ratio - simple) / simple > 0.025, (look, period, clock)


def test_a_hanging_companion_rests_its_tail_on_the_compositor():
    # atlasidle2 (2026-11-07): hanging from its perch it is still, but "hang" was not a calm
    # state, so the tail redrew nine paths 11 times a second (66 restyles of ~70 animated
    # elements in 6 s). It is a rest of the lower body (`atlasRigLower.rests`); the tail rests too.
    assert re.search(r'atlasTailCalm\.states = new Set\(\[[^\]]*"hang"', LIFE)
    rests = re.search(r"atlasRigLower\.rests = new Set\(\[([^\]]*)\]", LIFE).group(1)
    calm = re.search(r"atlasTailCalm\.states = new Set\(\[([^\]]*)\]", LIFE).group(1)
    assert "hang" in rests and "hang" in calm


def test_the_pacer_has_no_breath_animation_to_step():
    # The companion's pacer (avatars.js, `nameMarkBuddyTempo`) steps what animates inside a drawing;
    # the breath is no animation now, so it has nothing to skip for it.
    av = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    assert 'a.id !== "atl-breath"' not in av
    assert 'id: "atl-breath"' not in LIFE
