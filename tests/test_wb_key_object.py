"""Align to a key object (INBOX 1313, plan row 3): the key's box is the
reference and the key stays put."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")


def _reference(entries, key):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = WB.index("function wbAlignReference(")
    fn = WB[start : WB.index("\n}\n", start) + 3]
    script = fn + f"const r = wbAlignReference({json.dumps(entries)}, {json.dumps(key)});console.log(JSON.stringify({{box: r.box, moving: r.moving.map(e => e.id)}}));"
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def _entry(i, x0, x1):
    return {"kind": "object", "id": i, "bbox": {"minX": x0, "maxX": x1, "minY": 0, "maxY": 10}}


def test_the_key_is_the_reference_and_does_not_move() -> None:
    out = _reference([_entry(1, 0, 10), _entry(2, 50, 90), _entry(3, 20, 30)], "object:2")
    assert out["box"]["minX"] == 50 and out["moving"] == [1, 3]


def test_without_a_key_the_outer_box_is_the_reference() -> None:
    out = _reference([_entry(1, 0, 10), _entry(2, 50, 90)], None)
    assert (out["box"]["minX"], out["box"]["maxX"]) == (0, 90) and out["moving"] == [1, 2]


def test_a_key_outside_the_selection_is_ignored_and_cleared() -> None:
    assert "wbKey.object = null;" in WB
    out = _reference([_entry(1, 0, 10), _entry(2, 50, 90)], "object:9")
    assert out["moving"] == [1, 2]


def test_the_command_is_a_row() -> None:
    row = next(line for line in CMD.splitlines() if '{ id: "key-object"' in line)
    assert 'group: "Arrange"' in row and 'needs: "two"' in row and "wbSetKeyObject()" in row
