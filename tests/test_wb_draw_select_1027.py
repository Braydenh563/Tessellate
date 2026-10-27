"""A drawn shape is selected and the tool returns to Select (the owner,
2026-10-27; WHITEBOARD_PLAN decision 44). The pen and highlighter keep their
tool so strokes continue. Undo is the one `create` entry, so one step."""

from __future__ import annotations

from pathlib import Path

WB = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _commit_block() -> str:
    start = WB.index('const res = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify(sketchData) });')
    return WB[start:start + 1600]


def test_a_shape_commit_selects_it_and_returns_to_select():
    block = _commit_block()
    assert "!isFreehand" in block
    assert 'selectWbItem("sketch", res.id)' in block
    assert 'wbSelectToolRef?.("select")' in block


def test_the_create_undo_entry_is_still_a_single_step():
    block = _commit_block()
    assert block.count("wbPushUndo(") == 1
    assert 'wbPushUndo({ action: "create", kind: "sketch", id: res.id })' in block


def test_the_selection_follows_the_render_and_the_pen_is_untouched():
    block = _commit_block()
    assert block.index("renderWhiteboardNow()") < block.index('selectWbItem("sketch", res.id)')
    # The switch is guarded by the shape branch only.
    guard = block.index("if (!isFreehand)")
    assert guard < block.index('wbSelectToolRef?.("select")')
