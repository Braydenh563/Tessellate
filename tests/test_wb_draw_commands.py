"""draw.io's missing arrange and edit commands (WHITEBOARD_PLAN, "The draw.io
programme" sections 2, 4 and 11; whiteboard-1018 step 5): select all shapes,
select all connectors, turn 90 degrees, remove from group, copy and paste
size, grow a shape to fit its words, and reverse a connector.

They are rows in `WB_COMMANDS`, so the palette, the menus and the shortcut
sheet all offer them, and `tests/test_wb_commands.py` holds each row's words.
The connector's swap is a pure function and runs in node here; the app
measures the rest."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")

ROWS = {
    "select-shapes": ("Edit", "wbSelectAllOfKind"),
    "select-connectors": ("Edit", "wbSelectAllOfKind"),
    "turn-90": ("Arrange", "wbTurnSelection"),
    "remove-from-group": ("Arrange", "wbRemoveFromGroup"),
    "copy-size": ("Edit", "wbCopySize"),
    "paste-size": ("Edit", "wbPasteSize"),
    "auto-size": ("Edit", "wbAutoSizeSelection"),
    "reverse": ("Item", "wbReverseSelection"),
}


@pytest.mark.parametrize("cmd_id", sorted(ROWS))
def test_the_command_is_a_row_and_its_function_exists(cmd_id):
    group, fn = ROWS[cmd_id]
    row = next((line for line in CMD.splitlines() if f'{{ id: "{cmd_id}"' in line), None)
    assert row, cmd_id
    assert f'group: "{group}"' in row and 'surface: "board"' in row
    assert f"{fn}(" in row
    assert f"function {fn}(" in FMT or f"function {fn}(" in WB, fn


def test_the_needs_tests_exist():
    for need in ("reversible", "grouped", "sizeCopied"):
        assert f"  {need}: " in CMD, need
    for cmd_id, need in (("reverse", "reversible"), ("remove-from-group", "grouped"), ("paste-size", "sizeCopied"), ("copy-size", "one")):
        row = next(line for line in CMD.splitlines() if f'{{ id: "{cmd_id}"' in line)
        assert f'needs: "{need}"' in row, cmd_id


def test_each_change_is_one_undo_step():
    for fn in ("wbTurnSelection", "wbRemoveFromGroup", "wbPasteSize", "wbAutoSizeSelection", "wbReverseSelection"):
        src = FMT if f"function {fn}(" in FMT else WB
        body = src[src.index(f"function {fn}("):][:2500]
        assert "wbRecordGesture(" in body, fn


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_a_connector_reversed():
    def grab(name: str) -> str:
        start = WB.index(f"function {name}(")
        if start > 0 and WB[start - 6:start] == "async ":
            start -= 6
        depth, i = 0, WB.index("{", start)
        while True:
            depth += WB[i] == "{"
            depth -= WB[i] == "}"
            i += 1
            if depth == 0:
                return WB[start:i]

    src = FMT + "\n" + WB
    start = FMT.index("function wbReversedLinkFields(")
    depth, i = 0, FMT.index("{", start)
    while True:
        depth += FMT[i] == "{"
        depth -= FMT[i] == "}"
        i += 1
        if depth == 0:
            reverse_fn = FMT[start:i]
            break
    assert src
    script = "\n".join([grab("wbLinkCaps"), grab("wbLinkLabelT"), reverse_fn,
        """
const a = wbReversedLinkFields({
  type: "link-straight", sourceId: 1, sourceKind: "node", targetId: 2, targetKind: "sketch",
  sourceAnchor: { x: 1, y: 0.5 }, targetAnchor: { x: 0, y: 0.5 },
  startCap: "none", endCap: "arrow", startCapSize: "s", endCapSize: "l",
  points: [{ x: 1, y: 2 }, { x: 3, y: 4 }], bend: 40, label_t: 0.25,
});
const b = wbReversedLinkFields({ type: "link-curved", sourceId: 5, targetId: 6, endStyle: "end", sourcePoint: { x: 9, y: 9 } });
console.log(JSON.stringify({ a, b }));
"""])
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    out = json.loads(run.stdout)
    a, b = out["a"], out["b"]
    assert (a["sourceId"], a["targetId"], a["sourceKind"], a["targetKind"]) == (2, 1, "sketch", "node")
    assert a["sourceAnchor"] == {"x": 0, "y": 0.5} and a["targetAnchor"] == {"x": 1, "y": 0.5}
    assert (a["startCap"], a["endCap"], a["startCapSize"], a["endCapSize"]) == ("arrow", "none", "l", "s")
    assert a["points"] == [{"x": 3, "y": 4}, {"x": 1, "y": 2}]
    assert a["bend"] == -40 and a["label_t"] == 0.75
    # The old endStyle shape reads as caps, and is dropped once they are written.
    assert (b["startCap"], b["endCap"]) == ("arrow", "none") and "endStyle" not in b
    assert b["targetPoint"] == {"x": 9, "y": 9} and "sourcePoint" not in b
    assert b["sourceId"] == 6 and b["targetId"] == 5


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_auto_size_only_grows():
    start = FMT.index("function wbAutoSizeFactors(")
    depth, i = 0, FMT.index("{", start)
    while True:
        depth += FMT[i] == "{"
        depth -= FMT[i] == "}"
        i += 1
        if depth == 0:
            break
    script = FMT[start:i] + """
console.log(JSON.stringify([
  wbAutoSizeFactors({ w: 50, h: 40 }, { w: 100, h: 60 }),
  wbAutoSizeFactors({ w: 50, h: 90 }, { w: 100, h: 60 }),
  wbAutoSizeFactors({ w: 150, h: 30 }, { w: 100, h: 60 }),
  wbAutoSizeFactors({ w: 10, h: 10 }, { w: 0, h: 0 }),
]));
"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert out[0] == {"sx": 1, "sy": 1}
    assert out[1] == {"sx": 1, "sy": 1.5}
    assert out[2] == {"sx": 1.5, "sy": 1}
    assert out[3] == {"sx": 1, "sy": 1}
