"""The note editor is two surfaces, the bar and the slash menu (L-ui-modernisation-39).

UI_MODERNISATION_PLAN 13.2, the Note editor row: "the editor's bar, the
selection bar, the inline AI and the slash menu are four surfaces for one
task ... fold the four into two (bar and slash); the capture box shows the
text first". Inline AI was already document-only (`inlineAiAvailable`). The
selection bar is withheld on a note box that has its own bar, and the two
actions only it carried (Turn into, Ask Atlas about this selection) live in
that bar; Heading and Quote are rows of Turn into. The bar sits under the
text, and Template sits with the other adders. Measured with
`scratchpad/ui-sweeps/notesurface.js` and the session's probe.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text, documents_text, frontend_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _body(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    after = re.search(r"\n(?:async )?function ", text[start + 1 :])
    return text[start : start + 1 + after.start()] if after else text[start:]


def _strip() -> str:
    start = HTML.index('id="note-toolbar"')
    return HTML[start : HTML.index("</div>", start)]


def test_the_selection_bar_stands_down_on_a_note_box_with_its_own_bar() -> None:
    """Source text: "fold the four into two (bar and slash)". A note box whose
    formatting bar is on the page (`[data-md-target]` naming it) gets no
    selection bar; a note box without one (the quick note, the capture card)
    keeps it, since there it is the only place formatting lives."""
    show = _body(frontend_text("editor.js"), "selectionBarShow")
    assert 'editorSurfaceKind(textarea) === "note"' in show
    assert "data-md-target" in show and "return false" in show
    restore = _body(frontend_text("selection.js"), "selectionRestoreOnContextMenu")
    assert "selectionBarShow(surface) !== false" in restore, (
        "a right-click must not swallow the browser's menu when the bar stood down"
    )


def test_every_action_the_note_selection_bar_had_is_on_the_note_bar() -> None:
    """Source text: "every action that existed must stay reachable". The
    selection bar's formatting is on the strip by `data-md`; Heading and Quote
    are rows of Turn into; Turn into and Ask are the strip's own buttons."""
    editor = frontend_text("editor.js")
    actions = editor.split("const SELECTION_BAR_ACTIONS = [", 1)[1].split("];", 1)[0]
    md = set(re.findall(r'md: "([a-z0-9]+)"', actions))
    strip = _strip()
    on_strip = set(re.findall(r'data-md="([a-z0-9]+)"', strip))
    turn_rows = frontend_text("documents-prose.js").split("const DOC_TURN_INTO = [", 1)[1].split("];", 1)[0]
    turned = set(re.findall(r'\["([a-z0-9]+)"', turn_rows))
    missing = md - on_strip - turned
    assert not missing, f"note selection bar actions with no home on the bar: {sorted(missing)}"
    assert re.search(r'<button[^>]*data-turn[^>]*title="Turn into', strip)
    assert re.search(r'<button[^>]*data-ask[^>]*title="Ask Atlas about this selection"', strip)


def test_the_bar_runs_turn_into_and_ask_for_its_own_box() -> None:
    """Source text: "Replace, do not layer". The strip's delegated click runs
    the same two functions the selection bar called, for the box it names, so
    the edit form's clone works as Capture's does."""
    wire = _body(documents_text(), "wireMarkdownToolbar")
    assert "button[data-turn]" in wire and "docTurnIntoMenu(boxId" in wire
    assert "button[data-ask]" in wire and "askAboutSelection(" in wire


def test_the_capture_text_comes_first() -> None:
    """Source text: "the capture box shows the text first". The formatting
    strip sits under the text in Capture and in the edit form, and Template
    is an adder in the "Add to this note" row, not above the text."""
    composer = HTML[HTML.index('<div class="note-composer">') :]
    composer = composer[: composer.index('class="note-composer-foot"')]
    assert composer.index('id="entry-title"') < composer.index('id="entry-content"') < composer.index('id="note-toolbar"')
    tools = HTML[HTML.index("capture-tools-row") :]
    tools = tools[: tools.index("capture-filing-row")]
    assert 'id="entry-template"' in tools
    head = HTML[HTML.index('<section class="card" id="capture">') : HTML.index('id="capture-help-hint"')]
    assert 'id="entry-template"' not in head
    panels = frontend_text("note-edit-panels.js")
    assert "surface.append(titleInput, meta, textarea, toolbarEl)" in panels


def test_help_moves_with_the_bar() -> None:
    """Source text: "Help moves with the UI". The capture hint and the Guide
    say where Turn into and Ask are on a note."""
    hint = HTML[HTML.index('id="capture-help-hint"') :]
    hint = hint[: hint.index("</div>")]
    assert "Turn into" in hint and "Ask Atlas" in hint
    core = (ROOT / "src" / "tessellate" / "ai" / "help_topics_core.py").read_text(encoding="utf-8")
    assert "Turn into and Ask Atlas" in core
    tail = (ROOT / "src" / "tessellate" / "ai" / "help_topics_core_tail.py").read_text(encoding="utf-8")
    assert "a note's formatting bar" in tail
    assert "selectionBarShow" in app_js_text()
