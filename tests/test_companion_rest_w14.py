"""The companion at rest (W14, owner decision Q10; audit-1108-perf P1 and P5).

Measured with the companion on, the page at rest restyled and laid out 30 to
45 times a second (the dress morph at 10 Hz, the pacer at 20 Hz, the tail's
settle, a glance or a mood every few seconds). Two seconds from the last
input, not walking and doing nothing, the drawn loops stop; the first input
starts them again in the next frame. A key typed in a field is not input, so
typing with it at rest costs what typing with it off costs. Fixed clock, fakes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
LIFE = (JS / "atlas-life.js").read_text(encoding="utf-8")
AVATARS = (JS / "avatars.js").read_text(encoding="utf-8")
MICRO = (JS / "atlas-micro.js").read_text(encoding="utf-8")
ATLAS = (JS / "atlas.js").read_text(encoding="utf-8")
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _block(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i : src.index(end, i)]


@needs_node
def test_resting_needs_two_quiet_seconds_a_calm_state_and_no_act() -> None:
    code = (
        "const atlasTailCalm = () => {};\n"
        'atlasTailCalm.states = new Set(["idle", "sit"]);\n'
        "let clock = 10000;\nconst performance = { now: () => clock };\n"
        + _block(LIFE, "atlasTailCalm.rest = {", "//: Entering a rest pauses")
        + r"""
const buddy = (cls) => ({ className: cls });
const box = (cls) => ({ closest: () => (cls === null ? null : buddy(cls)) });
const at = (ms, cls, state) => { clock = 10000 + ms; return atlasTailCalm.resting(box(cls), state); };
atlasTailCalm.rest.at = 10000;
process.stdout.write(JSON.stringify({
  fresh: at(500, "", "idle"),
  quiet: at(2500, "", "idle"),
  walking: at(2500, "nmb-walking", "idle"),
  act: at(2500, "nmb-act-juggle", "idle"),
  thinking: at(2500, "nmb-think", "idle"),
  busyState: at(2500, "", "glide"),
  large: at(2500, null, "idle"),
}));
"""
    )
    run = subprocess.run(["node", "-e", code], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    got = json.loads(run.stdout)
    assert got == {"fresh": False, "quiet": True, "walking": False, "act": False, "thinking": False, "busyState": False, "large": False}


def test_the_drawn_loops_ask_whether_it_rests() -> None:
    # The morph timer, the pacer, the saccade, the glance clock, the mood drift and the tail's act pick.
    assert "atlasTailCalm.rest.sync(box, low.state)" in LIFE
    assert "atlasTailCalm?.rest.on" in AVATARS and "nameMarkBuddyTempo" in AVATARS
    assert "atlasTailCalm?.rest.on" in MOTION
    assert "atlasTailCalm?.rest.on" in MICRO
    assert "atlasTailCalm?.rest.on" in ATLAS
    assert "atlasTailCalm.resting(box, tail.state)" in LIFE


def test_input_wakes_in_the_next_frame_and_typing_in_a_field_is_not_input() -> None:
    wake = _block(LIFE, 'for (const type of typeof document.addEventListener', "//: On the function, not the shared scope")
    assert "setTimeout(() => r.wake.forEach" in wake, "the wake is not the input handler's cost"
    assert 'type === "keydown" && event.key !== "Enter"' in wake and "input, textarea, select, [contenteditable]" in wake


def test_a_key_does_not_rewrite_the_drowsy_class() -> None:
    # `remove` writes the attribute even when the class is absent: one restyle of the companion per key.
    assert 'if (buddy.classList.contains("nmb-drowsy")) buddy.classList.remove("nmb-drowsy");' in AVATARS


def test_a_blink_does_not_wake_the_rig() -> None:
    assert re.search(r"replace\(/\\batl-blinking\\b/g", MOTION)
