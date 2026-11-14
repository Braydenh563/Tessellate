"""Pins for LEDGER rows found already built on 2026-11-12 (documents closeout): each one fails if the behaviour goes."""

from __future__ import annotations
from tests._app_js import frontend_text

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_l297_lint_tooltip_is_empty_while_the_pointer_menu_is_open():
    code = _read("frontend", "js", "documents-code.js")
    assert "tooltipFilter: (diagnostics) => (docPointerMenuOpen() ? [] : diagnostics)" in code
    assert "CM.lint.linter(docCodeLintSource(CM), DOC_LINT_CONFIG)" in code


def test_l299_console_line_and_assistant_share_one_height():
    css = _read("frontend", "css", "library-lazy.css")
    line = css[css.index(".cm-console-line {") :][:400]
    assert "padding: var(--space-1) var(--space-3)" in line
    field = css[css.index(".cm-console-line > .cm-console-input {") :][:400]
    assert "height: var(--control-h)" in field and "border: 0" in field
    for rule in (".search-field.doc-assist-form {", ".doc-assist-asks > button.ghost,\n.doc-assist-tools > button.ghost {"):
        assert "height: var(--control-h)" in css[css.index(rule) :][:200]
    send = css[css.index("#doc-assist-send {") :][:200]
    assert "height: calc(var(--control-h) - 8px)" in send


def test_l306_documents_view_reads_doccmview_only_after_it_exists():
    view = _read("frontend", "js", "documents-view.js")
    assert 'typeof docCmView !== "undefined" && docCmView' in view
    assert 'lazyScript("/js/documents.js").then(() => lazyScript("/js/documents-ide.js"))' in view


def test_l340_link_offer_ignores_are_kept_on_the_notebook():
    prose = _read("frontend", "js", "documents-prose.js")
    assert "link_offer_ignored" in prose and 'method: "PUT"' in prose.split("async function docLinkOfferIgnore", 1)[1][:600]
    assert "docLinkOfferIgnore(finding.name)" in frontend_text("documents.js")


def test_l_documents_13_the_selection_bar_carries_the_note_button_on_a_phone():
    editor = _read("frontend", "js", "editor.js")
    assert '{ note: true, label: "ph:note-pencil"' in editor
    shown = editor.split("const note = bar.querySelector", 1)[1][:200]
    assert "editorSurfaceKind" in shown and "innerWidth" not in shown and "matchMedia" not in shown
    assert "[data-note]" not in "".join(p.read_text(encoding="utf-8") for p in CSS.glob("*.css"))


def test_l_documents_16_the_diagram_head_menu_has_every_export():
    embed = _read("frontend", "js", "diagram-embed.js")
    rows = embed[embed.index("function headExport()") :][:900]
    for label in ("Download as .png", "Download as .svg", "Copy as picture", "Copy as Mermaid", "Copy as SVG"):
        assert label in rows


def test_l290_diagram_blocks_topic_keeps_headroom_and_the_kind_menu_rows_are_direct_children():
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "diagram-blocks")
    assert len(body) <= 1860  # was 1896 of 1900
    kindbar = _read("frontend", "js", "diagram-kindbar.js")
    assert '[...menu.querySelectorAll(":scope > .menu-item")]' in kindbar
    assert 'className = "menu-item" + (item.danger' in _read("frontend", "js", "menus.js")
