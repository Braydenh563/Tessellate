"""A folded map keeps its size, so it is still framed when it opens again.

The owner, 2026-10-10: "I collapsed and opened the local map and the stuff
disappeared??". Collapsing the local map gives its box no size; `gcResize`
read that as its 800x540 fallback and the ResizeObserver framed the map for
a box that big, so on the way open every note was off the 226x176 canvas
(scratchpad/ui-sweeps/graphpanecollapse.js: 16 of 16 notes on the canvas
before, 0 after; 16 after the fix).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parent.parent
CANVAS = unwrapped((ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def _function(name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", CANVAS).start() + 1
    return CANVAS[start : CANVAS.index("\n}\n", start) + 2]


SCRIPT = _function("gcResize") + """
let box = { clientWidth: 226, clientHeight: 176 };
const document = { getElementById: () => box };
const window = { devicePixelRatio: 1 };
const canvas = { style: {} };
const s = { canvas, boxId: "graph-pane-box", size: "pane", dims: { w: 0, h: 0 } };
const first = gcResize(s);
box = { clientWidth: 0, clientHeight: 0 };
const folded = gcResize(s);
const whileFolded = { ...s.dims };
box = { clientWidth: 226, clientHeight: 176 };
const opened = gcResize(s);
const never = { canvas: { style: {} }, boxId: "x", size: "pane", dims: { w: 0, h: 0 } };
box = { clientWidth: 0, clientHeight: 0 };
gcResize(never);
console.log(JSON.stringify({ first, folded, whileFolded, opened, after: s.dims, never: never.dims }));
"""


@pytest.fixture(scope="module")
def run():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", SCRIPT], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_a_folded_box_changes_nothing(run):
    assert run["first"] is True
    assert run["folded"] is False, "a resize to nothing must not reframe the map"
    assert run["whileFolded"] == {"w": 226, "h": 176}


def test_opening_again_is_the_size_it_had(run):
    assert run["opened"] is False and run["after"] == {"w": 226, "h": 176}


def test_a_box_never_measured_still_gets_the_fallback(run):
    assert run["never"] == {"w": 800, "h": 540}
