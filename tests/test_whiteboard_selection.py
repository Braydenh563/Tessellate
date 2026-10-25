"""The whiteboard's selection affordances, as text.

The suite cannot open a board, so these hold the two facts the owner reported
missing: a sweep that catches one shape selects it the way a click does (which
is what draws its box and its eight anchors), and an anchor answers a double
click by fitting the box to its text.
"""

from __future__ import annotations

from pathlib import Path
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CSS = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))


def test_a_one_item_sweep_becomes_the_single_selection() -> None:
    """Reported: "shapes like circles and lines dont visibly select and show
    anchor points when I highlight select over them". The anchors are drawn by
    `wbRenderSketchHandles`, which only runs for the single selection, and a
    marquee put everything in the multi set. Both sweeps (marquee and lasso)
    promote a lone item now, so there are two copies of this."""
    assert WB.count("if (wbMultiSelection.size === 1) {") == 2


def test_a_swept_shape_has_a_style_of_its_own() -> None:
    """A sweep that caught several has no one box to hang anchors off, so the
    class itself has to say something."""
    assert ".sketch-group.wb-selected .sketch-hitbox {" in CSS


def test_an_anchor_answers_a_double_click_by_fitting_the_text() -> None:
    assert "async function wbFitToText(el)" in WB
    assert '.closest?.(".wb-resize-handle, .wb-map-resize-grip")' in WB
    #: Measured from the element's own layout, never estimated from the text.
    assert 'el.style.height = "auto";' in WB
    assert "el.scrollHeight" in WB


def test_a_multi_selection_gets_one_box_with_working_anchors() -> None:
    """Reported with two screenshots: "the highlight select only highlights the
    shapes, it doesnt show the box and enchor points as it should like when I
    individually select them". The group box scales its items through the same
    transform a single shape's handles use, so the two cannot drift apart."""
    assert "function wbRenderMultiSelectionHandles()" in WB
    assert "wbRenderMultiSelectionHandles();" in WB
    body = WB[WB.index("function wbRenderMultiSelectionHandles()") :]
    body = body[: body.index("\nfunction wbRenderSketchHandles()")]
    assert "wbSketchResizeTransform(bbox, handle, rawDX, rawDY" in body
    #: A render mid-drag would replace the handle the gesture is bound to.
    assert "wbScheduleRender();" not in body.split('.on("end"')[0].split('.on("drag"')[1]


def test_a_swept_shape_gets_its_own_box_and_the_group_keeps_the_grips() -> None:
    """Two reports, one rule.

    The owner, with a screenshot of a selected face beside two selected notes:
    "when I drag select shapes, the individual anchor/rotate boxes dont appear
    ... its fine for the notes but the shapes and lines arent selected visually
    and individually". A card keeps its handles as children, so the class alone
    reveals them; a shape is a path with nowhere to keep any, and only this
    function draws them.

    Then INBOX 278, after every member got a full set: "the rotate line and
    circle dont sit at the top center of a group selection ... and instead sit
    off to the top left or right, or below the top border". Measured on a
    three-item group: four rotate knobs, two stems and sixteen member resize
    handles on screen at once, so whichever stem the eye lands on rises from a
    member's own centre rather than the group box's.

    What answers both: a member of a group is drawn with its outline and
    nothing else, and the grips belong to the group. A shape selected on its
    own is unchanged and still gets all of them."""
    assert "function wbDrawSketchHandles(sketch, { outlineOnly = false } = {})" in WB
    assert (
        "if (row.entry.kind === \"sketch\") wbDrawSketchHandles(row.entry.item, { outlineOnly: true });"
        in WB
    ), "a member of a group selection is outlined, not given grips (INBOX 278)"
    assert "if (outlineOnly) return;" in WB, (
        "the outline-only mode has to stop before the eight handles, or it is "
        "the same full set under another name"
    )
    #: The lone selection, which must keep everything: `wbRenderSketchHandles`
    #: is the single-item path and passes no options.
    lone = WB[WB.index("function wbRenderSketchHandles()") :]
    lone = lone[: lone.index("\n//:")]
    assert "wbDrawSketchHandles(sketch);" in lone, (
        "a shape selected on its own keeps its own box, its eight anchors and "
        "its rotate grip: that is the report the outline-only mode must not "
        "undo"
    )
    #: And a card or a text box in a group hides its own grips by class, since
    #: it carries them as children rather than having them drawn.
    #: Toggled only when it changes (the marquee release touches only what moved, INBOX 410).
    assert 'el.classList.toggle("wb-in-group", grouped);' in WB
    assert ".node-card.wb-in-group .wb-rotate-handle" in CSS
    assert ".wb-object.wb-in-group .wb-resize-handle" in CSS


def test_the_group_box_has_a_rotate_point() -> None:
    """Asked for in the same message: "the group boxes dont have a rotate point
    at the top". Every item turns about the group centre, which for a card is a
    move and a rotation, and for a shape is baked into its path."""
    body = WB[WB.index("function wbRenderMultiSelectionHandles()") :]
    body = body[: body.index("\nfunction wbRenderSketchHandles()")]
    assert 'attr("class", "wb-sketch-rotate-handle")' in body
    assert "wbSketchAngleFromCenterDeg(" in body
    assert "item.rotation = (row.rotation + angle) % 360;" in body


def test_a_group_corner_scales_proportionally() -> None:
    """Reported: "when I try to resizr the multiple selected objects with the
    group box, the items all go out of proportion and funky". One shape
    stretching on one axis is a reshape you asked for; a set doing it turns
    every circle into a different ellipse."""
    assert "const corner = handle.length === 2;" in WB
    assert "const t = corner && !free ? { ...raw, sx: k, sy: k } : raw;" in WB


def test_a_drag_snaps_the_movement_not_the_position() -> None:
    """Reported: dragging "doesnt stay on the mouse and goes off to the side of
    where my mouse was on the object". Rounding the absolute position moves an
    off-grid item up to half a cell the instant the drag starts, and it stays
    that far from the cursor; rounding the delta keeps the grab point."""
    # The delta is snapped, not the position; Shift may zero one axis of it
    # (the one-axis drag, `wbAxisLock`), which is still a delta.
    assert WB.count('d.x = d._dragOriginX + (lock === "y" ? 0 : wbSnap(d._rawX - d._dragOriginX, bypassSnap));') == 2
    assert WB.count('d.y = d._dragOriginY + (lock === "x" ? 0 : wbSnap(d._rawY - d._dragOriginY, bypassSnap));') == 2


def test_the_board_owns_undo_while_it_is_open() -> None:
    """Reported: "ctrl z undo and redo cont trigger in the whiteboard/mind
    map". Two listeners matched the chord and whichever stack was non-empty
    answered. The board's own binding is gone and app.js hands it over."""
    app = app_js_text()
    assert 'return { where: "board", undo: () => window.wbUndo()' in app
    assert "await surface.undo();" in app
    assert "window.wbUndo = wbUndo;" in WB
    assert "wbUndo();\n      return;" not in WB


def test_every_undo_door_leads_to_the_board_while_one_is_open() -> None:
    """Asked for directly: "make sure redo is handled too. the undo and redo
    buttons in the bottom bar should work across the whole application". The
    status bar's buttons, the Ctrl+Z chord and the palette all go through
    performUndo/performRedo, which is where the handoff lives."""
    app = app_js_text()
    assert "function boardHistoryActive()" in app
    #: One decision for every door: the board's history, a document's, or
    #: the app's (the owner, 2026-10-05: "local undos and redos").
    assert app.count("const surface = surfaceHistory();") >= 2
    assert app.count("const surface = surfaceHistory(\"redo\");") >= 1
    assert "canUndo: window.wbCanUndo, canRedo: window.wbCanRedo" in app
    assert "canUndo: window.docCanUndo, canRedo: window.docCanRedo" in app
    assert "window.wbCanUndo = () => (wbHistoryFor(), wbUndoStack.length > 0);" in WB
    #: Each board keeps its own pair of stacks for the session.
    assert "const wbHistoryByBoard = new Map();" in WB


def test_the_group_outline_follows_the_drag() -> None:
    """Reported: "the group selection outline doesnt resize with the objects
    selected in side them when resizing or rotating the group selection". Every
    part of the chrome was positioned once from the box as it stood when the
    selection was made, so a drag left the outline and its anchors behind."""
    body = WB[WB.index("function wbRenderMultiSelectionHandles()") :]
    body = body[: body.index("\nfunction wbRenderSketchHandles()")]
    assert "function layoutGroupChrome(box)" in body
    assert "const live = scaledBox(t);\n            layoutGroupChrome(live);" in body
    #: A rotation turns the outline with its contents rather than leaving a
    #: level box round a turned set, and is dropped before the render.
    assert 'group.attr("transform", `rotate(${angle} ${centerX} ${centerY})`);' in body
    assert 'group.attr("transform", null);' in body
