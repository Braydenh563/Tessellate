"""INBOX 1400 and 1306: the force view "feels very messy to look at".

Measured with `gm.js` (the graph-1026 remaining file has the numbers): on the
36-note seed at 1440x900 the map was 0.49 of the canvas wide and 0.80 tall,
10 names drawn, and one note held 24 of 64 links, its spokes 24 bows fanning
across every cluster. These hold the pure pieces in node: the landscape pull,
the hub threshold, a hub's straight spokes, and the label pass's culling.
"""

import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
WORKER = (ROOT / "frontend" / "js" / "graph-worker.js").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _const(text: str, name: str) -> str:
    return re.search(rf"^const {name} = .*?;$", text, re.M).group(0) + "\n"


def _run(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _pulls(aspect: float) -> dict:
    script = (
        f"let world = {{ aspect: {aspect} }};\n"
        + _const(WORKER, "LANDSCAPE_PULL_MAX")
        + _function(WORKER, "landscapePull")
        + _function(WORKER, "portraitPull")
        + "const l = landscapePull(), p = portraitPull();"
        + "console.log(JSON.stringify({ l, x: 0.015 * p / Math.sqrt(l), y: 0.02 * Math.sqrt(l) }))"
    )
    return _run(script)


def test_a_landscape_map_is_pulled_wider_than_tall_and_keeps_its_size() -> None:
    wide = _pulls(0.5)  # a 1400x700 canvas
    assert wide["l"] == 3  # capped
    # A spring layout's extent goes as 1/sqrt(pull): x now spreads further than y.
    assert (wide["y"] / wide["x"]) ** 0.5 > 1.9
    # The product of the two pulls is unchanged, so the cloud's area holds.
    assert abs(wide["x"] * wide["y"] - 0.015 * 0.02) < 1e-12


def test_a_square_or_portrait_map_keeps_the_pulls_it_had() -> None:
    assert _pulls(1)["l"] == 1
    tall = _pulls(2)
    assert tall["l"] == 1 and tall["y"] == 0.02  # the 430 rule's portrait pull is untouched


def test_a_hub_is_three_times_the_mean_and_never_under_eight_links() -> None:
    fn = _const(CANVAS, "GC_HUB_SPOKES") + _function(CANVAS, "gcHubSpokeMin")
    out = _run(fn + "console.log(JSON.stringify([gcHubSpokeMin([24,3,3,4,2,3,1,4,5,2]), gcHubSpokeMin([1,1,2,1]), gcHubSpokeMin([]) === Infinity]))")
    assert out == [16, 8, True]  # mean 5.1, three times is 15.3


def test_a_hubs_spokes_are_straight_and_quieter_than_a_bridge() -> None:
    fn = _function(CANVAS, "gcBowPoint")
    out = _run(
        fn
        + "const a = {id: 'a', x: 0, y: 0, _hub: true}, b = {id: 'b', x: 100, y: 0}, c = {id: 'c', x: 100, y: 0};"
        + "console.log(JSON.stringify([gcBowPoint(b, a), gcBowPoint(a, b), gcBowPoint({id:'d',x:0,y:0}, c)]))"
    )
    assert out[0] == {"x": 50, "y": 0} and out[1] == {"x": 50, "y": 0}
    assert out[2]["y"] != 0  # an ordinary link still bows
    look = _function(CANVAS, "gcEdgeLook")
    assert "GC_HUB_SPOKE_ALPHA" in look and "a._hub || b._hub" in look


def test_the_label_pass_never_keeps_two_overlapping_names() -> None:
    rng = random.Random(1400)
    items = []
    for i in range(60):
        x, y, w = rng.uniform(0, 400), rng.uniform(0, 300), rng.uniform(60, 180)
        items.append({
            "id": i, "rank": rng.randint(0, 3), "force": False, "landmark": i < 8,  # a forced name (searched, hovered) is drawn regardless
            "left": x - w / 2, "right": x + w / 2, "top": y + 8, "bottom": y + 22, "x": x, "y": y + 15,
            "alts": [{"x": x, "y": y - 15, "left": x - w / 2, "right": x + w / 2, "top": y - 22, "bottom": y - 8}],
        })
    discs = [{"id": it["id"], "x": it["x"], "y": it["y"] - 15, "r": 5} for it in items]
    fn = _function(CANVAS, "gcPlaceLabels") + _function(CANVAS, "gcClampBox")
    out = _run(fn + f"console.log(JSON.stringify(gcPlaceLabels({json.dumps(items)}, {json.dumps(discs)})))")
    assert 0 < len(out) < len(items)  # some culled, some named
    for i, a in enumerate(out):
        for b in out[i + 1 :]:
            assert not (a["left"] < b["right"] and a["right"] > b["left"] and a["top"] < b["bottom"] and a["bottom"] > b["top"]), (a, b)
