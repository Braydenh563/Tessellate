"""R11/R12 leftovers (owner 2026-11-12): the sheet of existing diagrams, the Embed row's picker, the first branch off a decision,
key hints on touch, and a diagram's list and chat words. Source reads; the numbers are in the Playwright sweep named in HISTORY."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_the_sheet_lists_diagrams_and_new_in_the_dialog_of_choices():
    suggest = _js("diagram-suggest.js")
    body = suggest[suggest.index("async function choose(") : suggest.index("diagramModel.suggest = {")]
    assert 'file_type === "mmd"' in body and "New diagram" in body
    assert 'setAttribute("role", "radiogroup")' in body and "doc-template-choice" in body
    assert "items, choose }" in suggest and "diagramModel.suggest.choose(options)" in _js("documents-mermaid.js")


def test_a_text_box_and_a_board_ask_before_the_builder_and_new_is_empty():
    mermaid = _js("documents-mermaid.js")
    assert "pickExistingDiagram" not in mermaid
    door = mermaid[mermaid.index("async function diagramDoor") :]
    assert 'chooseDiagram({ verb: "Embed" })' in door and 'source: "",' in door
    assert "Add a block first, or Cancel." in door
    board = _js("whiteboard-interchange.js")
    edit = board[board.index("async function wbEditDiagram") :]
    assert 'chooseDiagram({ verb: "Insert" })' in edit and 'source: d?.data?.mermaid || ""' in edit
    assert "diagram_id" in board[board.index("async function wbInsertDiagram") : board.index("async function wbEditDiagram")]


def test_the_embed_row_reopens_the_picker_when_the_lists_arrive_late():
    editor = _js("editor.js")
    start = editor.index("function editorOpenMenu(")
    warm = editor[editor.index('if (trigger === "[[") {', start) : editor.index("\n}\n", start)]
    assert 'editorOpenMenu(editorMenuState.textarea, "[[")' in warm


def test_the_first_branch_off_a_decision_asks_for_its_words():
    builder = _js("diagram-builder.js")
    add = builder[builder.index("function addBlock(") : builder.index("function nameOnPicture")]
    assert 'joins(S, "ask", edge).then(name)' in add


def test_key_hints_are_not_shown_on_touch():
    assert "(pointer: coarse)" in _js("diagram-steps.js")[:3000]
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    assert "  .dgm-keychip {\n    display: none;\n  }\n}" in css[css.index("(pointer: coarse)", css.index("@container (max-width: 599.98px)")) :]


def test_a_diagram_row_says_diagram_not_a_word_count():
    assert 'doc.file_type === "mmd") return "Diagram"' in _js("library.js")
    assert 'row.file_type === "mmd" ? "diagram"' in _js("chat-attach.js")
