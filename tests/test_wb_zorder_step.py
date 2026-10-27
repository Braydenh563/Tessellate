"""Bring forward and Send backward move one step, not to the end (FEAT-07).

The features audit (2026-10-05, `scratchpad/audit1005/features.md`): with A
z1, B z2, C z3, one "Bring forward" on A gave `A:4 B:2 C:3`, so A went from
the bottom to the top. Every competitor's `]` and `[` are one step;
Ctrl+] and Ctrl+[ are to the front and to the back. `wbZOrderStepPlan` is
the pure half: given the layer's peers and one item, the z values to write.
Run in node against the source; the browser half is
`scratchpad/ui-sweeps/wb1005-zorder.js`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _plan(peers: list, key: str, direction: int) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        _function("wbBoxesOverlap")
        + _function("wbZOrderStepPlan")
        + f"\nconsole.log(JSON.stringify(wbZOrderStepPlan({json.dumps(peers)}, {json.dumps(key)}, {direction})));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return {k: z for k, z in json.loads(out.stdout.strip())}


def _box(x: float) -> dict:
    return {"minX": x, "minY": 0, "maxX": x + 100, "maxY": 100}


def _stack(*zs: int) -> list:
    """Three overlapping items A, B, C at the given z values."""
    return [{"key": name, "z": z, "box": _box(10 * i)} for i, (name, z) in enumerate(zip("ABC", zs))]


def _order(peers: list, changes: dict) -> str:
    zs = {p["key"]: changes.get(p["key"], p["z"]) for p in peers}
    return "".join(sorted(zs, key=lambda k: (zs[k], "ABC".index(k))))


def test_bring_forward_passes_one_item_not_all_of_them() -> None:
    peers = _stack(1, 2, 3)
    changes = _plan(peers, "A", 1)
    assert _order(peers, changes) == "BAC"


def test_send_backward_passes_one_item() -> None:
    peers = _stack(1, 2, 3)
    assert _order(peers, _plan(peers, "C", -1)) == "ACB"


def test_tied_layers_still_step_and_keep_the_rest_in_order() -> None:
    """A fresh board has every item at z 0: order is the array's then."""
    peers = _stack(0, 0, 0)
    changes = _plan(peers, "A", 1)
    assert _order(peers, changes) == "BAC"


def test_the_step_skips_items_it_does_not_overlap() -> None:
    """The next item that is actually over it, as draw.io and Figma do."""
    peers = [
        {"key": "A", "z": 1, "box": _box(0)},
        {"key": "B", "z": 2, "box": _box(5000)},
        {"key": "C", "z": 3, "box": _box(20)},
    ]
    changes = _plan(peers, "A", 1)
    zs = {p["key"]: changes.get(p["key"], p["z"]) for p in peers}
    assert zs["A"] > zs["C"]


def test_hidden_peers_are_passed_over() -> None:
    peers = _stack(1, 2, 3)
    peers[1]["skip"] = True
    changes = _plan(peers, "A", 1)
    assert _order(peers, changes) == "BCA"


def test_already_at_the_top_writes_nothing() -> None:
    assert _plan(_stack(1, 2, 3), "C", 1) == {}


def test_only_what_moved_is_written() -> None:
    peers = [{"key": k, "z": z, "box": _box(0)} for k, z in (("A", 1), ("B", 5), ("C", 9))]
    assert set(_plan(peers, "A", 1)) == {"A"}


def test_four_labelled_rows_and_the_keys_say_so() -> None:
    arrange = INDEX[INDEX.index('id="wb-arrange-menu"') :]
    arrange = arrange[: arrange.index("</div>\n        </div>")]
    for words in ("Bring forward", "Send backward", "Bring to front", "Send to back"):
        assert words in arrange, words
    assert "Ctrl+]" in arrange and "Ctrl+[" in arrange
    #: The right-click menu takes its rows from the same table.
    menu = SOURCE[SOURCE.index("function wbBuildContextMenu(") :]
    menu = menu[: menu.index("\n}\n")]
    for command in ("order-forward", "order-backward", "order-front", "order-back"):
        assert f'"{command}"' in menu, command


def test_sketches_paint_in_z_order() -> None:
    """A shape's z was written and never read: SVG paints in DOM order."""
    render = SOURCE[SOURCE.index("function renderWhiteboard()") :]
    render = render[: render.index("// Render Nodes (Cards)")]
    #: Placed in stack order by the bands (decision 43), which replaced d3's
    #: `sort`: a stroke can paint between two cards now.
    assert "wbPlaceSketchBands(" in render
