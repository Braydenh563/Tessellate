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
CSS = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")
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
    script = swell + "\n" + _fn("atlasBreathFrame") + "\n" + body
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


FAKE = """
const made = (look, rise) => {
  const torsos = [0, 1].map(() => ({ animated: [], animate(frames, opts) { const a = { frames, opts, started: null, cancelled: false, cancel() { this.cancelled = true; } }; this.animated.push(a); return a; } }));
  return {
    dataset: { atlasLook: look },
    querySelectorAll: () => torsos,
    querySelector: () => (rise ? { getAnimations: () => [rise] } : null),
  };
};
const anim = (ms, start) => ({ playState: "running", startTime: start, currentTime: 0, effect: { getComputedTiming: () => ({ duration: ms }) } });
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_chest_swells_on_the_rise_clock_and_rests_when_still():
    out = _run(
        FAKE
        + """
const res = {};
const box = made("masculine", anim(4600, 1234));
atlasBreathFrame(box, true);
const a = box.atlasTorsos[0].animated[0];
res.n = box.atlasTorsos.map((t) => t.animated.length);
res.frames = a.frames.map((f) => f.transform);
res.duration = a.opts.duration;
res.start = a.startTime;
res.iterations = a.opts.iterations === Infinity;
const fem = made("feminine", null);
atlasBreathFrame(fem, true);
res.fem = fem.atlasTorsos[0].animated[0].opts.duration;
const still = made("masculine", anim(4600, 0));
atlasBreathFrame(still, true);
atlasBreathFrame(still, false);
res.still = still.atlasTorsos.map((t) => t.animated[0].cancelled);
res.cleared = still.atlasBreath === null;
process.stdout.write(JSON.stringify(res));
"""
    )
    assert out["n"] == [1, 1], "one animation per torso"
    assert out["frames"] == ["scale(1, 1)", "scale(1.035, 1.025)", "scale(1, 1)"], "starts and ends at rest; the peak is a few percent, wider than tall"
    assert out["duration"] == 4600 and out["start"] == 1234 and out["iterations"], "the rise's period and start time: one clock"
    assert out["fem"] == 4000, "her breath is 4 s when no rise is running"
    assert out["still"] == [True, True] and out["cleared"], "still by setting, off screen or hidden: back at rest"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_breath_is_set_once_and_not_written_each_step():
    out = _run(
        FAKE
        + """
const box = made("masculine", anim(4600, 0));
for (let i = 0; i < 300; i += 1) atlasBreathFrame(box, true);
const steady = box.atlasTorsos.map((t) => t.animated.length);
box.dataset.atlasLook = "feminine";
atlasBreathFrame(box, true);
const retuned = box.atlasTorsos.map((t) => [t.animated.length, t.animated[0].cancelled]);
process.stdout.write(JSON.stringify({ steady, retuned }));
"""
    )
    assert out["steady"] == [1, 1], "300 steps at rest start one animation, not 300 writes"
    assert out["retuned"] == [[2, True], [2, True]], "a new look (a new period) replaces it"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_breath_waits_out_the_entrance_fade():
    # Started under the companion's opacity-0 entrance, a boot-built torso animation
    # is refused by the compositor for good (compositeFailed bit 17, an empty box;
    # measured: both torsos refused on the reload path, none when started later).
    out = _run(
        FAKE
        + """
let opacity = "0";
globalThis.getComputedStyle = () => ({ opacity });
const box = made("masculine", anim(4600, 0));
box.closest = () => ({});
atlasBreathFrame(box, true);
const early = box.atlasTorsos ? box.atlasTorsos.map((t) => t.animated.length) : [0, 0];
opacity = "1";
atlasBreathFrame(box, true);
atlasBreathFrame(box, true);
process.stdout.write(JSON.stringify({ early, late: box.atlasTorsos.map((t) => t.animated.length) }));
"""
    )
    assert out["early"] == [0, 0], "nothing is started while the figure is faded out"
    assert out["late"] == [1, 1], "started once, on the first beat after the fade"


def test_it_rides_the_tail_loop_which_knows_the_motion_gates():
    frame = _fn("atlasTailFrame")
    # And behind the lock (`data-atlas-hidden`, Brief 34 decision 7).
    assert "const live = atlasMotionOK(box) && !box.classList.contains(\"atl-off\") && !document.hidden && !document.documentElement.hasAttribute(\"data-atlas-hidden\");" in frame
    # Called before the loop skips its odd frames, so a still figure is put
    # back at rest by the one frame the loop draws then.
    assert frame.index("atlasBreathFrame(box, live);") < frame.index("if (live && tail.tick % 2 && tail.drawn && !tail.calm)")


def test_only_the_torso_breathes_and_it_composes():
    body = _fn("atlasBreathFrame")
    assert '".atl-layer-body .nmb-torso"' in body
    # A `transform` animation, not the individual `scale`: that is refused on an svg box (compositeFailed bit 19).
    assert "transform:" in body and "el.animate(" in body
    assert "style.scale" not in body and "composite" not in body, "not an add: tests/test_atlas_composite_1101.py"
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


def test_the_pacer_leaves_the_breath_on_the_compositor():
    # The companion's pacer (avatars.js, `nameMarkBuddyTempo`) pauses and steps by hand whatever
    # animates inside a drawing: it held the torso's breath and wrote its currentTime 33 times a
    # second, a restyle of every animated element each time (hooks.js, 131 writes in 4 s).
    av = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    tempo = av[av.index("function nameMarkBuddyTempo()") :]
    pick = tempo[: tempo.index("nmbTempo.slow = new WeakSet")]
    assert 'a.id !== "atl-breath"' in pick
    assert 'id: "atl-breath"' in LIFE
