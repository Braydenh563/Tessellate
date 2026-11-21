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
