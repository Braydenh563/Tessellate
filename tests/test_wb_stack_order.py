"""The board's one stacking order (wbz-1026, the layer-order pair sweep).

Four sites used to decide what is on top, each its own way: the SVG sort
(z, id), the cards' z-index (z, then whichever element the DOM happened to
append last), the export (frames, then every drawing, then every card, then
every object, in array order) and the Layers tab (z, then id across kinds).
`wbStackOrder` is now the one answer they all read; these tests pin its
rules. Run in node against the source; the browser half is the pair sweep
recorded in `docs/roadmap/agent-remaining/wbdog-1026.md`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
SOURCE = "\n".join((JS / f"{name}.js").read_text(encoding="utf-8") for name in ("whiteboard", "whiteboard-library"))


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _const(name: str) -> str:
    start = SOURCE.index(f"const {name} =")
    return SOURCE[start : SOURCE.index(";\n", start) + 2]


def _run(expr: str, state: dict) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        _const("WB_STACK_KIND_RANK")
        + "".join(_function(n) for n in ("wbStackBand", "wbStackCompare", "wbStackOrder", "wbStackNewZ"))
        + f"\nconst wbState = {json.dumps(state)};\nconsole.log(JSON.stringify({expr}));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _keys(state: dict) -> list:
    return _run("wbStackOrder(wbState).map((e) => e.key)", state)


def test_frames_paint_below_drawings_and_drawings_below_cards() -> None:
    state = {
        "sketches": [{"id": 1, "z": 50}],
        "nodes": [{"id": 1, "z": -5}],
        "objects": [{"id": 1, "kind": "frame", "z": 99}, {"id": 2, "kind": "text", "z": -9}],
    }
    assert _keys(state) == ["object:1", "sketch:1", "object:2", "node:1"]


def test_z_orders_within_a_band() -> None:
    state = {
        "sketches": [],
        "nodes": [{"id": 7, "z": 3}],
        "objects": [{"id": 1, "kind": "text", "z": 4}, {"id": 2, "kind": "table", "z": 2}],
    }
    assert _keys(state) == ["object:2", "node:7", "object:1"]


def test_a_tie_breaks_as_a_reload_paints_notes_then_objects_then_id() -> None:
    state = {
        "sketches": [{"id": 9, "z": 1}, {"id": 3, "z": 1}],
        "nodes": [{"id": 20, "z": 1}, {"id": 2, "z": 1}],
        "objects": [{"id": 1, "kind": "image", "z": 1}],
    }
    assert _keys(state) == ["sketch:3", "sketch:9", "node:2", "node:20", "object:1"]


def test_a_missing_z_counts_as_zero() -> None:
    state = {"sketches": [], "nodes": [], "objects": [{"id": 1, "kind": "text", "z": None}, {"id": 2, "kind": "text", "z": -1}]}
    assert _keys(state) == ["object:2", "object:1"]


def test_a_new_item_goes_on_top_of_its_own_band() -> None:
    state = {
        "sketches": [{"id": 1, "z": 5}],
        "nodes": [{"id": 1, "z": 10}],
        "objects": [{"id": 1, "kind": "frame", "z": 40}, {"id": 2, "kind": "text", "z": 2}],
    }
    assert _run('wbStackNewZ("object", { kind: "text" })', state) == 11
    assert _run('wbStackNewZ("node")', state) == 11
    assert _run('wbStackNewZ("sketch")', state) == 6


def test_a_new_frame_goes_under_the_frames_already_there() -> None:
    state = {"sketches": [], "nodes": [{"id": 1, "z": -30}], "objects": [{"id": 1, "kind": "frame", "z": 4}]}
    assert _run('wbStackNewZ("object", { kind: "frame" })', state) == 3
    assert _run('wbStackNewZ("object", { kind: "frame" })', {"sketches": [], "nodes": [], "objects": []}) == 0


def test_every_site_reads_the_one_order() -> None:
    """The render, the export, the Layers tab, the hit test and the order
    commands each call the shared order rather than sorting for themselves."""
    for name in ("wbBuildExportSvg", "wbLayerRows", "wbLayerRestack", "wbLockedItemAt", "wbZOrderPeers", "renderWbObjects"):
        body = _function(name)
        assert "wbStack" in body, name
    assert ".sort((a, b) => (a.z || 0) - (b.z || 0) || a.id - b.id)" not in SOURCE
    assert '.style("z-index", d => d.z)' not in SOURCE
    assert '.style("z-index", (d) => d.z)' not in SOURCE


def test_inserts_make_their_drawings_on_top_not_at_a_fixed_z() -> None:
    """wb5: Mermaid, draw.io, Join, the library's Place joined and a dragged
    link wrote z 1, 2 or 3, so they landed under or over what was there. The
    library's own placement is stacked on the server (`_stack_on_top`)."""
    import re

    for name in ("whiteboard-interchange", "whiteboard-commands", "whiteboard-library"):
        text = (JS / f"{name}.js").read_text(encoding="utf-8")
        fixed = re.findall(r"x: 0, y: 0, z: \d+,? ?\n? *board_id", text)
        assert fixed == [], (name, fixed)
    interchange = (JS / "whiteboard-interchange.js").read_text(encoding="utf-8")
    assert "post = async (data, z" not in interchange
    assert interchange.count('z: wbStackNewZ("sketch")') >= 6
