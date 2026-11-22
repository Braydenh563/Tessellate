"""A mind map topic's data may only change through the board's undo store (INBOX 1625).

The owner could not undo a glow, and asked that every action across the app
undo and redo. `wbMapSetNodeStyle` records the step for every look the strip,
the rings and the menus set, so the class to guard is a path that writes a
topic's `data` some other way, or that passes `undo: false`, without reaching
the store. This reads `whiteboard.js` and `whiteboard-map.js`, splits them
into top-level functions, and fails on a function that writes `.data = {...`
(or calls `wbMapSetNodeStyle(..., { undo: false`) and neither reaches a
recorder nor is listed in `WB_RECORDED`, nor sits in `EXEMPT` with a reason.

A second rule guards what made the glow stay on screen after Undo: the node
is painted outside the render (`wbPaintMapNodeStyle`), so the render's paint
key must be cleared there, or an Undo that restores the key's old data is
skipped as "unchanged".

`EXEMPT` may only shrink; the test fails on an entry no longer needed.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
FILES = ["whiteboard.js", "whiteboard-map.js"]

#: Names that put a step on the board's undo store (or record the whole gesture).
RECORDERS = ("wbPushUndo", "wbPushDragUndo", "wbPushMoveBatch", "wbPushCall", "wbRecordGesture")
DATA_WRITE = re.compile(r"\b\w+\.data\s*=\s*\{\s*\.\.\.")
UNDO_OFF = re.compile(r"wbMapSetNodeStyle\([^;]*undo:\s*false")
FUNC = re.compile(r"^(?:async )?function\s+(\w+)", re.M)

#: "function": "reason". The reason says where the step is recorded instead.
EXEMPT: dict[str, str] = {
    "wbReplaceWrite": "a helper; wbBoardReplaceAll pushes the one step for all rows",
    "wbMapPasteText": "every caller wraps it in wbRecordGesture (whiteboard-commands.js)",
    "wbMapPinOnDrag": "the drag's own step snapshots the topic before it is pinned",
    "wbOutlineIndent": "only a sort key before wbMapTransplant, which records the move",
    "wbOutlineOutdent": "only a sort key before wbMapOutdent, which is in WB_RECORDED",
}


def functions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in FILES:
        src = frontend_text(name)
        marks = [(m.start(), m.group(1)) for m in FUNC.finditer(src)]
        for i, (at, fn) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(src)
            out[fn] = out.get(fn, "") + src[at:end]
    return out


def recorded_names() -> set[str]:
    src = frontend_text("whiteboard.js")
    block = src[src.index("const WB_RECORDED = ["):]
    block = block[: block.index("];")]
    return set(re.findall(r'"(\w+)"', block))


def test_topic_data_writes_reach_the_undo_store():
    recorded = recorded_names()
    bad, used = [], set()
    for fn, body in functions().items():
        if not (DATA_WRITE.search(body) or UNDO_OFF.search(body)):
            continue
        #: `wbMapSetNodeStyle` records unless it is told `undo: false`; the
        #: bend and side drags write live frames and then call it for the step.
        if fn in recorded or any(r in body for r in RECORDERS):
            continue
        if "wbMapSetNodeStyle(" in body and not UNDO_OFF.search(body):
            continue
        if fn in EXEMPT:
            used.add(fn)
            continue
        bad.append(fn)
    assert not bad, (
        "These write a topic's data without reaching the undo store "
        f"(wbPushUndo, wbPushDragUndo, wbRecordGesture or WB_RECORDED): {bad}"
    )
    stale = set(EXEMPT) - used
    assert not stale, f"EXEMPT entries no longer needed: {sorted(stale)}"


def test_painting_a_node_outside_the_render_clears_its_paint_key():
    for fn, body in functions().items():
        if "wbPaintMapNodeStyle(" in body and fn not in ("wbPaintMapNodeStyle", "wbPaintMapNode"):
            assert "_wbPaintKey = null" in body, (
                f"{fn} paints a topic outside the render but leaves its paint key, "
                "so an Undo back to the key's old data is skipped and the old look stays"
            )
