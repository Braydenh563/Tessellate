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
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
LIFE = (ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", LIFE, re.S | re.M)
    assert match, f"{name} is gone from atlas-life.js"
    return match.group(0)


def _duration(rule_start: str) -> float:
    match = re.search(re.escape(rule_start) + r"[^}]*?(?:animation: [\w-]+ |animation-duration: )([0-9.]+)s", CSS)
    assert match, rule_start
    return float(match.group(1))


def _run(body: str):
    swell = "\n".join(re.search(rf"^const {n} = .*;$", LIFE, re.M).group(0) for n in ("ATLAS_BREATH_SWELL", "ATLAS_BREATH_STEP_MS"))
    script = swell + "\n" + _fn("atlasBreathFrame") + "\n" + body
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


FAKE = """
const torso = () => ({ style: { scale: "" } });
const made = (look, rise) => {
  const torsos = [torso(), torso()];
  return {
    dataset: { atlasLook: look },
    querySelectorAll: () => torsos,
    querySelector: () => (rise ? { getAnimations: () => [rise] } : null),
  };
};
const anim = (ms, at) => ({ effect: { getComputedTiming: () => ({ duration: ms }) }, currentTime: at });
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_chest_swells_on_the_rise_clock_and_rests_when_still():
    out = _run(
        FAKE
        + """
const res = {};
for (const at of [0, 1150, 2300, 3450, 4600]) {
  const box = made("masculine", anim(4600, at));
  atlasBreathFrame(box, true, 1000);
  res[at] = box.atlasTorsos[0].style.scale;
}
const still = made("masculine", anim(4600, 2300));
atlasBreathFrame(still, true, 1000);
atlasBreathFrame(still, false, 1010);
res.still = still.atlasTorsos.map((t) => t.style.scale);
const paced = made("masculine", anim(4600, 2300));
atlasBreathFrame(paced, true, 1000);
paced.atlasTorsos[0].style.scale = "marker";
atlasBreathFrame(paced, true, 1060);
res.within = paced.atlasTorsos[0].style.scale;
atlasBreathFrame(paced, true, 1100);
res.after = paced.atlasTorsos[0].style.scale;
process.stdout.write(JSON.stringify(res));
"""
    )
    assert out["0"] == "" and out["4600"] == "", "it starts and ends at rest, on the rise's clock"
    assert out["2300"] == "1.0350 1.0250", "the peak is a few percent, wider than tall"
    sx, sy = map(float, out["1150"].split())
    assert 1.015 < sx < 1.02 and 1.01 < sy < 1.015, out["1150"]
    assert out["still"] == ["", ""], "still by setting, off screen or hidden: back at rest"
    assert out["within"] == "marker", "ten a second by the clock: a frame 60 ms on writes nothing"
    # The rise's clock is read once a refresh and run on by the wall's
    # (tests/test_atlas_frame_reads.py): read at 2300 when the wall said 1000,
    # it is 2400 at 1100, a hair past the peak.
    assert out["after"] == "1.0348 1.0249"


def test_it_rides_the_tail_loop_which_knows_the_motion_gates():
    frame = _fn("atlasTailFrame")
    # And behind the lock (`data-atlas-hidden`, Brief 34 decision 7).
    assert "const live = atlasMotionOK(box) && !box.classList.contains(\"atl-off\") && !document.hidden && !document.documentElement.hasAttribute(\"data-atlas-hidden\");" in frame
    # Called before the loop skips its odd frames, so a still figure is put
    # back at rest by the one frame the loop draws then.
    assert frame.index("atlasBreathFrame(box, live, now);") < frame.index("if (live && tail.tick % 2 && tail.drawn && !tail.calm)")


def test_only_the_torso_breathes_and_it_composes():
    body = _fn("atlasBreathFrame")
    assert '".atl-layer-body .nmb-torso"' in body
    assert "el.style.scale = scale" in body, "the individual `scale`, so a gesture's transform composes"
    assert "style.transform" not in body
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
