"""K24: formatting part of a board text box or sticky while typing in it.

The owner: "the formatting bar only appears when the user is not editing ...
I want to be able to format specific parts of the text in text boxes and
sticky notes like I highlight a word and bold it". Measured by
`scratchpad/ui-sweeps/wbinlinefmt.js` on the base: the documents editor's
selection bar (`#selection-bar`, editor.js) already showed over a selection
in an edited box, but every press did nothing ("hello world" stayed "hello
world" after Bold) because `applyMarkdown` resolved its target by element id
and the box has none; Ctrl+B did nothing either. This pins the shape: one
bar, one `applyMarkdown`, the box's own surface as the target, every edit
through `insertText` so Ctrl+Z undoes it.
"""

from __future__ import annotations

import re

from tests._app_js import frontend_text


def _body(file: str, name: str) -> str:
    text = frontend_text(file)
    start = text.index(f"function {name}(")
    nxt = re.search(r"\n(?:async )?function ", text[start + 10 :])
    return text[start : start + 10 + (nxt.start() if nxt else len(text))]


def test_apply_markdown_reaches_the_box_being_edited():
    assert "wbEditorSurfaceById(id)" in _body("documents.js", "docSurfaceById")
    found = _body("whiteboard.js", "wbEditorSurfaceById")
    assert "document.activeElement" in found and "wbEditorSurface" in found


def test_the_boxs_edits_go_through_insert_text_so_undo_holds():
    surface = _body("whiteboard.js", "wbEditableSurface")
    assert "set selectionStart(" in surface and "set selectionEnd(" in surface
    splice = _body("whiteboard.js", "wbSpliceEditable")
    assert 'execCommand(insert ? "insertText"' in splice
    # The value setter and the "/" menu's splice both take the undoable path.
    assert surface.count("wbSpliceEditable(") >= 2


def test_ctrl_b_i_k_format_the_selection_in_a_box():
    keys = _body("whiteboard.js", "wbTextFormatKey")
    for kind in ('"bold"', '"italic"', '"link"'):
        assert kind in keys
    assert 'applyMarkdown(' in keys and '"wb-text-edit"' in keys
    assert "wbTextFormatKey(event)" in frontend_text("whiteboard.js")


def test_the_bar_on_a_board_keeps_the_seven_and_adds_a_list():
    assert "wbSelectionBarFit(bar, textarea)" in _body("editor.js", "selectionBarShow")
    fit = _body("whiteboard.js", "wbSelectionBarFit")
    assert 'boardMd = "ul"' in fit and "ph:list-bullets" in fit
    assert "WB_BAR_TEXT" in fit and "WB_BAR_TOPIC" in fit
    text = frontend_text("whiteboard.js")
    line = text[text.index("const WB_BAR_TEXT"):]
    line = line[: line.index("\n")]
    for md in ("bold", "italic", "strike", "code", "link", "highlight"):
        assert f'"{md}"' in line


def test_formatting_turns_the_rendered_view_on_for_that_box():
    text = frontend_text("whiteboard.js")
    assert "wbFormatted" in _body("whiteboard.js", "wbEditorSurfaceById")
    blur = text[text.index('content.on("blur", function () {'):]
    blur = blur[: blur.index("content.on(\"keydown\"")]
    assert "wbFormatted" in blur and "md: true" in blur


def test_the_guide_names_it():
    from tessellate.ai.help_topics_more import MORE_TOPICS  # noqa: PLC0415

    topic = next(t for t in MORE_TOPICS if t["id"] == "sticky-notes")
    assert "select words" in topic["body"] and "Ctrl+B" in topic["body"]
