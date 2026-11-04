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
    assert "#tab-documents.doc-is-diagram .doc-dock-menu-item[data-click-proxy]" in CSS


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
    for ident in ("doc-export-svg", "doc-export-picture", "doc-copy-picture"):
        assert f'id="{ident}"' in HTML and ident in DOCS
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
    button = HTML[HTML.index('id="doc-new-diagram"') - 60 : HTML.index('id="doc-new-diagram"') + 400]
    assert "ghost small icon-only" in button and 'aria-label="New diagram"' in button and "ph-flow-arrow" in button
    assert HTML.index('id="doc-new-template"') < HTML.index('id="doc-new-diagram"') < HTML.index('id="doc-new-diagram"') + 400
    assert '$("doc-new-diagram")?.addEventListener("click", () => diagramModel.door({ doc: true }));' in DOCS
    # About this list names it.
    assert "diagram button" in HTML[HTML.index('id="doc-list-help"') : HTML.index('id="doc-list-help"') + 1200]
