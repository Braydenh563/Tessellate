"""PF10 (audit 1031 row 19): a label fade asks for a label frame, not a whole one.

A name fading in at rest used to ask for a full repaint per display frame
(nebulae, links, dots, then names): 6 to 29 calls a second at 6 to 28 ms
each. The frame that starts a label-only fade keeps the canvas as it was
before the names (`s.labelFrame.base`); the frames after it copy that back
and paint only the names (`gcDrawLabels.frame`). Any other request for a draw
drops the copy, so a camera move, a hover or new positions repaint whole.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import gc_frame, unwrapped

ROOT = Path(__file__).resolve().parent.parent
CANVAS = unwrapped((ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    found = re.search(rf"^function {name}\(.*?^\}}", CANVAS, re.S | re.M)
    assert found, name
    return found.group(0)


def _method(name: str) -> str:
    found = re.search(rf"^gcDrawLabels\.{name} = function .*?^\}};", CANVAS, re.S | re.M)
    assert found, name
    return found.group(0)


def _run(body: str) -> dict:
    script = "\n".join(
        [
            "const calls = [];",
            "const d3 = { zoomIdentity: { k: 1, x: 0, y: 0 } };",
            "const gcTokens = {};",
            "const gcRequestDraw = (s, cheap) => { calls.push(['request', cheap, Boolean(s.labelAsking)]); };",
            "gcRequestDraw.selfCap = 300;",
            "const gcFadeStep = () => 0.25;",
            "const gcStill = () => false;",
            "let labelResult = true;",
            "const gcDrawLabels = (ctx, s, placed, step, k) => { calls.push(['labels', placed.length, step, k]); return labelResult; };",
            _method("frame"),
            "const mk = () => { const canvas = {}; const base = {}; return {",
            "  canvas, ctx: { canvas, setTransform() {}, clearRect() {}, save() {}, restore() {}, translate() {}, scale() {},",
            "    drawImage(img) { calls.push(['drawImage', img === base]); } },",
            "  dims: { w: 100, h: 80 }, dpr: 1, transform: { k: 2, x: 5, y: 6 }, timing: { frames: 0, lastFrame: 0 },",
            "  labelFrame: { base, placed: [{ id: 1 }], k: 2, x: 5, y: 6, w: 100, h: 80, dpr: 1, tokens: gcTokens } }; };",
            body,
        ]
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout
    return json.loads(out)


@needs_node
def test_a_label_frame_copies_the_base_and_paints_only_the_names():
    out = _run(
        """
        const s = mk();
        const done = gcDrawLabels.frame(s);
        process.stdout.write(JSON.stringify({ done, calls, kept: Boolean(s.labelFrame) }));
        """
    )
    assert out["done"] is True
    kinds = [c[0] for c in out["calls"]]
    assert kinds == ["drawImage", "labels", "request"]
    assert out["calls"][0][1] is True
    # Still fading: asks for the next label frame, cheaply, as itself.
    assert out["calls"][2] == ["request", True, True]
    assert out["kept"] is True


@needs_node
def test_a_label_frame_ends_with_the_fade_and_lets_the_scene_compose_again():
    out = _run(
        """
        labelResult = false;
        const s = mk();
        s.sceneStale = true;
        const done = gcDrawLabels.frame(s);
        process.stdout.write(JSON.stringify({ done, calls, kept: Boolean(s.labelFrame), stale: s.sceneStale }));
        """
    )
    assert out["done"] is True
    assert [c[0] for c in out["calls"]] == ["drawImage", "labels"]
    assert out["kept"] is False
    assert out["stale"] is False


@needs_node
@pytest.mark.parametrize(
    "change",
    [
        "s.transform = { k: 3, x: 5, y: 6 };",
        "s.dims = { w: 120, h: 80 };",
        "s.dpr = 2;",
        "s.hoveredId = 4;",
        "s.dragNode = {};",
        "s.layoutRunning = true;",
        "s.ctx = { canvas: {} };",
        "s.labelFrame = null;",
        "s.selfFrames = 299;",
    ],
)
def test_anything_that_moved_since_the_base_was_kept_falls_back_to_a_whole_frame(change):
    out = _run(f"const s = mk(); {change} process.stdout.write(JSON.stringify({{ done: gcDrawLabels.frame(s), calls }}));")
    assert out["done"] is False
    assert out["calls"] == []


def test_the_draw_tries_the_label_frame_before_composing_and_keeps_the_base_only_for_a_label_fade():
    draw = gc_frame(CANVAS)
    assert draw.index("gcDrawLabels.frame(s)") < draw.index("gcDrawComposed(s)")
    # The copy is taken between the names' update and their paint, and only while fading.
    assert "gcDrawLabels(ctx, s, placedLabels, fadeStep, k, " in draw
    assert "s.labelFrame = " in draw


def test_any_other_draw_request_drops_the_kept_base():
    request = _fn("gcRequestDraw")
    assert "s.labelFrame = null" in request
    assert request.index("s.labelFrame = null") < request.index("s.drawQueued ||")
