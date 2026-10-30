"""One image control for every surface that shows a note's picture (INBOX 1465).

A picture's width and alignment live in its alt text (`![A river|300|center](url)`,
DOCUMENTS_PLAN decision 8). The Live editor draws and writes them (the note
form, the graph popup, the board card editor, the document editor); the
read-only renderers (a note card, the timeline's note view, a board card's
text, chat) used to draw the raw picture and ignore them, so an image centred
in the graph popup was left-aligned everywhere else. These tests pin the one
module (`image-layout.js`) that parses, draws and writes the options, and the
two places in the boot code that route a note's picture through it.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import JS_DIR, LAZY_PIECES, app_js_text

LAYOUT = (JS_DIR / "image-layout.js").read_text(encoding="utf-8")
DOCUMENTS = (JS_DIR / "documents.js").read_text(encoding="utf-8")
NOTES_LIST = (JS_DIR / "notes-list.js").read_text(encoding="utf-8")
TIMELINE_DETAIL = (JS_DIR / "timeline-detail.js").read_text(encoding="utf-8")
APP = (JS_DIR / "app.js").read_text(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def test_the_module_is_lazy_and_loads_before_the_document_editor():
    assert "image-layout.js" in LAZY_PIECES
    bundle = re.search(r"library: \[(.*?)\n  \],", APP, re.S).group(1)
    assert bundle.index("/js/image-layout.js") < bundle.index("/js/documents.js")


def test_the_parsers_and_the_control_have_one_home():
    for name in ("imageOptions", "imageAltWith", "imageOptionsFromAlt", "imageApplyOptions", "imageWireEdit"):
        assert re.search(rf"^function {name}\(", LAYOUT, re.M), name
        assert not re.search(rf"^function {name}\(", DOCUMENTS, re.M), f"{name} is defined twice"
    # the old names are gone, not aliased (replace, do not layer)
    assert "docImageOptions" not in app_js_text()
    assert "docWireImageEdit" not in app_js_text()


def test_both_inline_pictures_in_a_note_card_are_handed_to_the_layout():
    # the plain picture and the card's thumbnail, each after it is in the page;
    # a hook, not a helper, because the boot scripts are at their byte budget
    assert NOTES_LIST.count("window.imageLayout?.(img)") == 2
    renderer = NOTES_LIST[NOTES_LIST.index("if (imageUrl !== undefined)") :][:3200]
    assert renderer.index("element.appendChild(img);") < renderer.index("window.imageLayout?.(img)")
    # one builder for both: the class is the only difference
    assert renderer.count('createElement("img")') == 1
    assert 'dismissible ? "attachment-thumb" : "entry-inline-image"' in renderer


def test_the_timeline_note_view_is_editable():
    assert "imageEdit" in TIMELINE_DETAIL


def test_saving_a_layout_writes_the_note_once_and_names_what_changed():
    # the save goes through the notes API like every other edit, replaces the
    # exact markdown it drew, and is one undo step
    save = LAYOUT[LAYOUT.index("async function imageSaveNote(") :][:1800]
    assert "/entries/" in save and "pushEntryPutUndo" in save
    assert "includes(raw)" in save
    # one PUT: the picture is never uploaded or re-read, only the text changes
    assert save.count('method: "PUT"') == 1 and "/media" not in save


def test_the_align_menu_offers_what_the_document_editor_offered():
    menu = LAYOUT[LAYOUT.index("openMenuAtPoint(") :][:900]
    for label in ("ph:text-align-left Left", "ph:text-align-center Centre", "ph:text-align-right Right", "ph:x Inline"):
        assert label in menu, label


def test_the_live_editor_hands_the_shared_control_its_own_write():
    live = DOCUMENTS[DOCUMENTS.index("function docImageLive(") :][:1500]
    assert "imageWireEdit(frame, options, { write, widest })" in live
    assert "imageAltWith(" in live


def test_the_center_and_right_rules_exist_for_a_picture_read_in_a_card():
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".cm-md-figure.cm-md-figure-center > :is(.md-picture, .thumb-wrap)" in css
    assert ".cm-md-figure.cm-md-figure-right > :is(.md-picture, .thumb-wrap)" in css
