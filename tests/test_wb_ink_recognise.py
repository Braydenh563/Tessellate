"""A rough hand-drawn stroke becomes a clean shape (L-whiteboard-3). `whiteboard-ink-recognise.js` is pure and run in node on
seeded wobbly strokes; the browser half (the command, one Undo step) is `scratchpad/ui-sweeps/wbink3.js`."""

from __future__ import annotations

import json
import math
import random
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _recognise(points):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const wbFmtState = {};\n" + frontend_text("whiteboard-ink-recognise.js")
        + f"\nconsole.log(JSON.stringify(wbFmtState.inkRecognise.recognise({json.dumps(points)})));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def _wobble(points, seed, amount=2.5):
    rng = random.Random(seed)
    return [[x + rng.uniform(-amount, amount), y + rng.uniform(-amount, amount)] for x, y in points]


def _along(corners, closed, step=6.0):
    """Points every `step` along the polygon through `corners`."""
    out = []
    ring = corners + ([corners[0]] if closed else [])
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        out += [[x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n] for i in range(n)]
    out.append(list(ring[-1]))
    return out


def test_a_wobbly_line_is_a_line():
    out = _recognise(_wobble(_along([(10, 10), (310, 60)], False), 1))
    assert out["kind"] == "line" and out["d"].startswith("M ") and " L " in out["d"]


def test_a_shaft_with_a_head_is_an_arrow_pointing_at_the_far_end():
    stroke = _along([(10, 100), (300, 100), (270, 75), (300, 100), (270, 125)], False)
    for seed in range(2, 8):
        out = _recognise(_wobble(stroke, seed, 1.5))
        assert out and out["kind"] == "arrow", seed
        assert out["d"].split(" L ")[1].split()[0].startswith(("29", "30")), out["d"]


def test_a_wobbly_box_is_a_rectangle_in_its_own_box():
    out = _recognise(_wobble(_along([(20, 20), (220, 20), (220, 130), (20, 130)], True), 3))
    assert out["kind"] == "rect"
    assert " h " in out["d"] and out["d"].endswith("Z")


def test_a_wobbly_loop_is_an_ellipse():
    ring = [[120 + 100 * math.cos(t / 30 * 2 * math.pi), 80 + 60 * math.sin(t / 30 * 2 * math.pi)] for t in range(31)]
    out = _recognise(_wobble(ring, 4, 2))
    assert out["kind"] == "ellipse" and " a " in out["d"]


def test_three_corners_are_a_triangle_and_four_mid_side_corners_a_diamond():
    tri = _recognise(_wobble(_along([(100, 10), (200, 150), (10, 150)], True), 5))
    assert tri["kind"] == "triangle" and tri["d"].count(" L ") == 2
    dia = _recognise(_wobble(_along([(100, 10), (190, 80), (100, 150), (10, 80)], True), 6))
    assert dia["kind"] == "diamond"


def test_a_scribble_a_dot_and_a_zigzag_stay_as_they_are():
    rng = random.Random(7)
    scribble = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(40)]
    assert _recognise(scribble) is None
    assert _recognise([[5, 5], [6, 6], [5, 6]]) is None
    assert _recognise(_along([(0, 0), (60, 80), (120, 0), (180, 80), (240, 0)], False)) is None


def test_a_small_wobble_does_not_change_the_answer():
    base = _along([(20, 20), (220, 20), (220, 130), (20, 130)], True)
    kinds = {_recognise(_wobble(base, seed, 3))["kind"] for seed in range(8, 14)}
    assert kinds == {"rect"}


def test_the_recogniser_is_lazy_loaded_after_the_ink_file():
    entries = frontend_text("lazy-entries.js")
    assert entries.index("/js/whiteboard-ink-more.js") < entries.index("/js/whiteboard-ink-recognise.js")
