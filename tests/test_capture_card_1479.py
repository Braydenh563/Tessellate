"""INBOX 1479: the Notes tab's one-line capture bar and the card it opens into.

The owner showed a reference Notes panel: "Add a note..." on one line, opening
in place into a card (title, body, Close and Save). The bar is markup in
index.html (one line, no script of its own); the card is the lazy
capture-card.js, fetched on the bar's first focus so the boot scripts stay
under their gzip cap (tests/test_static_compression.py).
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import APP_JS, INDEX_HTML, LAZY_PIECES, app_js_files

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CARD = (JS / "capture-card.js").read_text(encoding="utf-8")
CARD_CSS = (ROOT / "frontend" / "css" / "capture-card-lazy.css").read_text(encoding="utf-8")
INDEX = INDEX_HTML.read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    nxt = re.search(r"\n(?:async )?function \w+\(", source[start + 10 :])
    return source[start : start + 10 + nxt.start()] if nxt else source[start:]


def test_the_bar_is_one_line_in_the_notes_tab_above_the_list():
    bar = INDEX.index('id="capture-bar"')
    assert INDEX.index('id="entries-heading"') < bar < INDEX.index('id="entry-list"')
    assert 'id="capture-bar-input"' in INDEX
    assert 'placeholder="Add a note…"' in INDEX


def test_the_card_is_a_lazy_file_not_a_boot_script():
    assert "capture-card.js" in LAZY_PIECES
    assert "capture-card.js" not in {p.name for p in app_js_files()}
    assert "/js/capture-card.js" in (JS / "notes-list.js").read_text(encoding="utf-8")
    assert "<script src=\"/js/capture-card" not in INDEX  # fetched on first focus, never a <script>


def test_escape_closes_and_ctrl_enter_saves():
    keys = _function_body(CARD, "captureCardKeys")
    assert '"Escape"' in keys and "closeCaptureCard" in keys
    assert 'event.key === "Enter"' in keys and "(event.ctrlKey || event.metaKey)" in keys
    assert "saveCaptureCard" in keys


def test_the_draft_is_kept_on_every_edit_and_dropped_on_save():
    assert 'const CAPTURE_DRAFT_KEY = "captureCardDraft"' in CARD
    keep = _function_body(CARD, "keepCaptureDraft")
    assert "prefs.set(CAPTURE_DRAFT_KEY" in keep and "prefs.remove(CAPTURE_DRAFT_KEY)" in keep
    assert "keepCaptureDraft()" in _function_body(CARD, "wireCaptureCard")
    assert "prefs.remove(CAPTURE_DRAFT_KEY)" in _function_body(CARD, "resetCaptureCard")


def test_save_goes_through_the_one_note_path_and_keeps_the_words_on_failure():
    save = _function_body(CARD, "saveCaptureCard")
    assert "createNoteSafely(" in save and "announceSavedNote(" in save
    assert "withTitle(" in CARD
    # a refusal leaves the card as it was, with the reason under it
    assert "catch (error)" in save and "captureCardStatus(" in save


def test_the_card_has_no_inline_style_and_no_em_dash_or_exclamation_in_copy():
    for text in (CARD, CARD_CSS):
        assert chr(0x2014) not in text
        assert 'setAttribute("style"' not in text and ".style.cssText" not in text
    copy = re.findall(r'"([A-Z][^"]{3,60})"', CARD)
    assert not [c for c in copy if c.endswith("!")]


def test_quick_note_and_the_card_share_the_saved_announcement():
    quick = (JS / "quick-note.js").read_text(encoding="utf-8")
    assert quick.count("function announceSavedNote(") == 1
    assert "announceSavedNote(saved" in _function_body(quick, "saveQuickNote")
    assert "capture-card.js" not in APP_JS.read_text(encoding="utf-8")

