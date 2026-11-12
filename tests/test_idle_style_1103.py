"""INBOX 1560, audit 1103: an idle companion and emblem must not keep style dirty.

The owner's Windows lag logs showed ~20 `UpdateLayoutTree` a second over a
621-element page with nothing happening, and "forced layout" in
`nameMarkBuddyBeat`. Traced (a30p-1103): the CSS loops are compositor-only and
cost nothing on their own; every restyle is a main-thread frame that some JS
asked for, and each such frame re-resolves every running animation (about 65
nodes in Atlas). The largest source was the animation pacer, which woke at
20 Hz and read `playState` of all its animations (a forced style each) to
step one that moves 5 times a second. These pin the fix and the rule.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
WIDGETS = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(name: str) -> str:
    start = AV.index(f"function {name}(")
    depth = 0
    for i in range(AV.index("{", start), len(AV)):
        depth += AV[i] == "{"
        depth -= AV[i] == "}"
        if depth == 0:
            return AV[start : i + 1]
    raise AssertionError(name)


def test_emblem_keyframes_animate_only_composited_properties() -> None:
    """The dashboard emblem's idle loops: transform and opacity, never a custom
    property (which would restyle every descendant on each frame) or a layout
    property."""
    blocks = re.findall(r"@keyframes (emblem-[\w-]+) \{(.*?)\n\}", WIDGETS, re.S)
    assert len(blocks) >= 4
    for name, body in blocks:
        props = set(re.findall(r"^\s*([\w-]+)\s*:", body, re.M))
        props.discard("animation-timing-function")
        assert props <= {"transform", "opacity"}, (name, props)


def test_pacer_wakes_no_faster_than_the_slowest_step_needs() -> None:
    """The pacer's next wake is a whole number of beats on, as far as its
    animations' own steps allow, and any state that can change a step
    (a running or still-unpaused animation) takes it back to every beat."""
    fn = _function("nameMarkBuddyTempo")
    assert "nmbTempo.stride" in fn
    assert "NMB_TEMPO_MS * nmbTempo.stride" in fn
    # The stride is spent on the beat it was set for: a beat never inherits one.
    assert re.search(r"const stride = nmbTempo\.stride;\s*nmbTempo\.stride = 1;", fn)
    # Only a beat with nothing running, nothing busy and no still-needed read sets one.
    assert "if (!busy && !still) nmbTempo.stride = nmbTempo.step(" in fn


@needs_node
@pytest.mark.parametrize(
    ("gaps", "states", "want"),
    [
        ([], [], 1),
        ([4], ["paused"], 4),
        ([4, 6], ["paused", "paused"], 2),
        ([4, 4], ["paused", "running"], 1),
        ([0], ["paused"], 1),
        ([3, 5], ["paused", "paused"], 1),
    ],
)
def test_stride_is_the_gcd_of_the_gaps_and_one_when_anything_runs(gaps, states, want) -> None:
    start = AV.index("nmbTempo.step = (")
    src = "const nmbTempo = {};\n" + AV[start : AV.index("\n};\n", start) + 4]
    script = (
        f"{src}\n"
        "const anims = " + str([{"i": i} for i in range(len(gaps))]).replace("'", '"') + ";\n"
        "const gaps = new Map(anims.map((a, i) => [a, " + str(gaps) + "[i]]));\n"
        f"process.stdout.write(String(nmbTempo.step(anims, {states!r}, gaps)));\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    assert out.stdout == str(want)
