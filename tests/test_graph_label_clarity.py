"""INBOX 1300 C41: "the force graph still gets a little messy and hard to look at".

The owner's screenshot: names on top of other notes, names that could belong
to either of two dots, lines between clusters as loud as those inside one,
and two notes both called "Ice Breakers:" with nothing to tell them apart.
Measured on the 57-note seed (`d2/probe.js`, 1440x900) before the change: at
the fit 6 of 16 names stood nearer another dot than their own; at 1.8x zoom 6
names sat under the dock, legend, minimap or zoom strip; a line between two
categories drew at 0.40 against 0.55 inside one; "Ice Breakers:" twice.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


PLACE = _function(CANVAS, "gcPlaceLabels") + _function(CANVAS, "gcClampBox")


def _box(id_, x, y, w=40, h=10, alts=()):
    return {
        "id": id_, "rank": 2, "force": False, "landmark": False,
        "left": x - w / 2, "right": x + w / 2, "top": y - h / 2, "bottom": y + h / 2,
        "x": x, "y": y, "alts": [
            {"x": ax, "y": ay, "left": ax - w / 2, "right": ax + w / 2, "top": ay - h / 2, "bottom": ay + h / 2}
            for ax, ay in alts
        ],
    }


def test_a_name_nearer_another_dot_than_its_own_is_not_placed_there() -> None:
    # Note 1 at (0,0). Its first place, under it at y 30, is 20 from note 2's
    # dot at (0,46) and 25 from its own: it reads as note 2's name. The second
    # place, above it, is clear and nearer its own dot.
    items = [_box(1, 0, 30, alts=[(0, -30)])]
    discs = [{"id": 1, "x": 0, "y": 0, "r": 5}, {"id": 2, "x": 0, "y": 46, "r": 5}]
    out = _run(PLACE + f"console.log(JSON.stringify(gcPlaceLabels({json.dumps(items)}, {json.dumps(discs)})))")
    assert len(out) == 1 and out[0]["y"] == -30, out


def test_a_name_with_only_ambiguous_places_is_left_for_the_hover() -> None:
    items = [_box(1, 0, 30)]
    discs = [{"id": 1, "x": 0, "y": 0, "r": 5}, {"id": 2, "x": 0, "y": 46, "r": 5}]
    out = _run(PLACE + f"console.log(JSON.stringify(gcPlaceLabels({json.dumps(items)}, {json.dumps(discs)})))")
    assert out == []


def test_names_stay_out_from_under_the_maps_overlays() -> None:
    body = _function(CANVAS, "gcOverlayBoxes")
    for selector in ("#graph-minimap", "#graph-zoom"):
        assert selector in body
    assert "GC_FIT_OVERLAYS" in body
    assert "gcOverlayBoxes(s" in CANVAS.replace(body, ""), "the label pass blocks the overlays"


def test_two_notes_with_one_title_are_told_apart() -> None:
    script = (
        "const GC_LABEL_FULL = 80; const gcKeyboardId = () => null;\n"
        "const clipText = (t, n) => (t.length > n ? t.slice(0, n - 1) + '…' : t);\n"
        "const GC_LABEL_SMALL_WORDS = new Set();\n"
        + _function(CANVAS, "gcLabelCut")
        + _function(CANVAS, "gcLabelText")
        + """
const s = { tree: null, hoveredId: null, adj: new Map(), dupTitles: new Set(["Ice Breakers:"]) };
const a = { id: 1, preview: "Ice Breakers:", category: "Work" };
const b = { id: 2, preview: "Ice Breakers:", category: "Courses & Study" };
const c = { id: 3, preview: "Standup notes", category: "Work" };
console.log(JSON.stringify([gcLabelText(a, s), gcLabelText(b, s), gcLabelText(c, s)]));
"""
    )
    a, b, c = _run(script)
    assert a != b and "Work" in a and "Courses" in b
    assert c == "Standup notes"


def test_a_line_between_two_categories_is_quieter_in_every_force_shape() -> None:
    look = _function(CANVAS, "gcEdgeLook")
    assert "_bridgeCat" in look
    assert "node._bridgeCat" in CANVAS
