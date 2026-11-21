"""L184: at rest the tail's beat stops, and input or a change of what the figure does wakes it.

Measured 2026-11-14 (L184 progress): with Motion at rest set to still, the tail's functions cost 17.6 ms a
minute, all of it the 400 ms rest beat (`ATLAS_TAIL_REST_BEAT_MS`) that rewrote the chest's swell and read
the rest gates. 2026-11-21 before this change (`tailcost.js`, 30 s, feminine, still): atlas-life.js 42.5 ms a
minute, `atlasBreathFrame.put` 24.4 of it. Now the beat ends once the figure is resting (`atlasTailCalm.resting`)
and leaves a waker: the input listeners call it, and so does the rig's observer (a class, a pose, a mood:
`atlasRigWake`, then `atlasTailWake`); the desk window's own state change calls `atlasTailCalm.rest.stir`.
The chest holds through the rest and goes on from the held phase, not a jump.
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
LIFE = unwrapped((ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8"))
DESK = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", LIFE, re.S | re.M)
    assert match, f"{name} is gone from atlas-life.js"
    return match.group(0)


def test_the_resting_beat_leaves_a_waker_and_sets_no_timer() -> None:
    frame = _fn("atlasTailFrame")
    hold = frame[frame.index("if (holds) {") :]
    hold = hold[: hold.index("\n  }\n") if "\n  }\n" in hold else len(hold)]
    rest_at = hold.index("atlasTailCalm.resting(box, tail.state)")
    timer_at = hold.index("setTimeout(")
    assert rest_at < timer_at, "the resting check comes before the 400 ms re-arm"
    between = hold[rest_at:timer_at]
    assert "atlasTailCalm.rest.wake.add(" in between and "return;" in between, "a resting figure leaves a waker and returns"
    assert "atlasTailWake(box)" in between, "the waker restarts the beat through the one wake path"


def test_a_desk_state_change_stirs_the_rest() -> None:
    assert re.search(r"atlasTailCalm\.rest\.stir = \(\) =>", LIFE), "one stir that calls every waker"
    show = DESK[DESK.index("function show(next)") :]
    show = show[: show.index("\n  }\n")]
    assert "atlasTailCalm?.rest.stir" in show, "the desk window's state change wakes a stopped beat"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_chest_goes_on_from_its_held_phase_after_a_rest() -> None:
    swell = re.search(r"^const ATLAS_BREATH_SWELL = .*;$", LIFE, re.M).group(0)
    put = re.search(r"^atlasBreathFrame\.put = .*?^\};", LIFE, re.M | re.S).group(0)
    script = (
        "let clock = 0;\nconst performance = { now: () => clock };\nconst atlasBreathFrame = {};\n" + swell + "\n" + put + "\n"
        + """
const torso = { style: { transform: "" } };
const box = { atlasTorsos: [torso], atlasBreath: { look: "feminine", anims: [], rate: 1, period: 4000, ph: 0, at: 0, rode: 0 } };
atlasBreathFrame.put(box, 800);
const held = box.atlasBreath.ph;
atlasBreathFrame.put(box, 61000);
const after = box.atlasBreath.ph;
atlasBreathFrame.put(box, 61100);
process.stdout.write(JSON.stringify({ held, after, next: box.atlasBreath.ph }));
"""
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert abs(out["held"] - 0.2) < 1e-9
    assert abs(out["after"] - out["held"]) < 1e-9, "a minute at rest does not jump the chest"
    assert abs(out["next"] - (out["held"] + 0.025)) < 1e-9, "and the breath runs on from there"
