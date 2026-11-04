"""INBOX 1679 slice 8: a diagram page, not a document page, and a way to start one that is not behind a chevron.

A diagram (.mmd) drops the prose editor's chrome (Format, Assistant, Snippets, How to edit, Focus mode, the Preview tab stop)
and keeps the title, the Canvas | Blocks | Source seg (one tab stop, arrows move inside it), About, More actions with its
three picture rows, and the builder's own bar. The numbers (Tab presses from the title to the first block, the stage's top at
1440x900) are a browser run named in docs/roadmap/agent-remaining/diagram-1679-1104.md.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    start = CSS.index(selector)
    return CSS[start : CSS.index("}", start)]


def test_a_diagram_marks_the_documents_tab_and_the_prose_chrome_goes_with_the_mark():
    assert '$("tab-documents")?.classList.toggle("doc-is-diagram", type.ext === "mmd");' in DOCS
    rule = _rule("#tab-documents.doc-is-diagram .doc-actions > :is(")
    for gone in ("#doc-code-format", "#doc-code-assist-open", "#doc-code-snippets-open", "#doc-focus-toggle", ".doc-view-cluster > .doc-view-menu"):
        assert gone in rule, gone
    assert "display: none;" in rule
    # The phone's proxy rows for those buttons go too, so the menu offers nothing that presses a hidden button.
    # Intent moved (review of 1679): the rule named every proxy row, which also took "AI edit" and "About these controls" off a phone's menu
    # while the desktop keeps both, so it now names only the rows that press a hidden button.
    assert "#tab-documents.doc-is-diagram .doc-dock-menu-item:is(" in CSS
    for proxy in ("doc-code-format", "doc-code-assist-open", "doc-code-snippets-open", "doc-focus-toggle"):
        assert f'[data-click-proxy="{proxy}"]' in CSS, proxy
    assert 'data-click-proxy="doc-ai"' not in CSS.split("doc-is-diagram .doc-dock-menu-item:is(")[1].split("{")[0]


def test_the_preview_is_not_a_tab_stop_for_a_diagram_and_is_again_for_a_document():
    assert '$("doc-preview").tabIndex = type.ext === "mmd" ? -1 : 0;' in DOCS


def test_the_diagram_seg_is_one_tab_stop_and_the_arrow_keys_move_inside_it():
    seg = DOCS[DOCS.index("syncDocFileType.diagramSeg = function (seg) {") :]
    seg = seg[: seg.index("\n};")]
    assert 'seg.addEventListener("keydown"' in seg and "ArrowRight" in seg and "ArrowLeft" in seg
    assert 'if (button.closest("#doc-diagram-seg")) button.tabIndex = on ? 0 : -1;' in DOCS
    # A view with no button on (Split) still leaves the seg reachable.
    assert "firstElementChild.tabIndex = 0" in DOCS


def test_the_export_menu_of_a_diagram_has_save_as_svg_png_and_copy_as_picture():
    # Intent moved, not weakened: the .svg row is built in documents.js (buildDiagramControls) because index.html is capped at a
    # fixed element count (test_boot_diet3); it still exists, with its label, right before the .png row.
    for ident in ("doc-export-picture", "doc-copy-picture"):
        assert f'id="{ident}"' in HTML and ident in DOCS
    build = DOCS[DOCS.index("function buildDiagramControls()") :][:1500]
    assert 'row.id = "doc-export-svg"' in build and "ph:file-svg Download as .svg" in build and 'add($("doc-export-picture"), "before", row)' in build
    assert 'id="doc-export-svg"' not in HTML
    # Wired to the diagram's own export (diagram-embed.js `out`), svg and png downloads, the picture copied.
    assert '[["doc-export-svg", "svg"], ["doc-export-picture", "png"], ["doc-copy-picture", "picture"]]' in DOCS
    assert "diagramModel.embed.out(how, docText(), currentDoc?.title)" in DOCS
    # Shown for a diagram only, and folded into Download or print with the other rows.
    assert 'for (const id of ["doc-export-svg", "doc-export-picture", "doc-copy-picture"]) $(id)?.classList.toggle("hidden", type.ext !== "mmd");' in DOCS


def test_the_builder_takes_the_pages_room_and_the_phones_list_head_is_two_lines():
    assert "padding-top: var(--space-2);" in _rule("#tab-documents.doc-is-diagram #doc-preview {")
    phone = CSS[CSS.index("#doc-sidebar-list > .sidebar-head {") :][:520]
    assert "flex-wrap: wrap;" in phone and "display: contents;" in phone and "var(--sidebar-toggle-size)" in phone


def test_diagram_is_a_button_beside_new_not_only_a_row_behind_the_chevron():
    # The blind tester missed it: the type menu behind New's caret was the only way (2 clicks). One icon button, the template button's neighbour.
    # Intent moved, not weakened: the button is built in documents.js (buildDiagramControls), not index.html, which is capped at a fixed
    # element count (test_boot_diet3). Same classes, label and icon, placed right after the template button.
    build = DOCS[DOCS.index("function buildDiagramControls()") :][:1500]
    assert 'b.className = "ghost small icon-only"' in build and 'b.setAttribute("aria-label", "New diagram")' in build and "ph ph-flow-arrow" in build
    assert 'add($("doc-new-template"), "after", b)' in build and 'id="doc-new-diagram"' not in HTML
    assert '$("doc-new-diagram")?.addEventListener("click", () => diagramModel.door({ doc: true }));' in DOCS
    # About this list names it.
    assert "diagram button" in HTML[HTML.index('id="doc-list-help"') : HTML.index('id="doc-list-help"') + 1200]
