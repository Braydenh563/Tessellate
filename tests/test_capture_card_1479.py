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
    assert '"/js/capture-card.js"' in (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'ensureModule("captureCard")' in (JS / "notes-list.js").read_text(encoding="utf-8")
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
    assert "createNoteSafely(" in save and "announceSavedNote(" in _function_body(CARD, "finishCaptureSave")
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


# --- step 2: To-do mode -------------------------------------------------------


def test_the_mode_switch_is_a_seg_in_the_bar_and_the_card():
    assert 'class="seg capture-bar-modes"' in INDEX
    assert 'data-mode="note"' in INDEX and 'data-mode="todo"' in INDEX
    assert '"seg capture-card-modes"' in _function_body(CARD, "captureModeSeg")
    assert "aria-pressed" in _function_body(CARD, "setCaptureMode")


def test_a_todo_saves_as_the_checklist_markdown_the_notes_list_already_draws():
    assert "- [ ] " in _function_body(CARD, "captureItemsToLines")
    assert "withTitle(" in _function_body(CARD, "captureCardContent")
    # the note card draws exactly this line as a round-ish box (`.entry-task`)
    lists = (JS / "notes-list.js").read_text(encoding="utf-8")
    assert r"\[([ xX])\]" in lists


def test_the_two_modes_convert_into_each_other_without_losing_lines():
    assert "captureLinesToItems" in CARD and "captureItemsToLines" in CARD
    assert "CAPTURE_TASK_LINE" in CARD


def test_rows_have_a_grip_an_x_and_an_add_and_move_by_keyboard_too():
    row = _function_body(CARD, "captureItemRow")
    assert "capture-card-grip" in row and "Remove this item" in row
    assert "capture-card-add" in CARD and "ph-plus" in CARD
    keys = _function_body(CARD, "captureItemKeys")
    assert "altKey" in keys and '"Backspace"' in keys and '"Enter"' in keys


def test_the_draft_keeps_the_mode_and_the_items():
    draft = _function_body(CARD, "captureCardDraft")
    assert "mode" in draft and "items" in draft


# --- step 3: colour, tags, the bell ---------------------------------------------

MORE = (JS / "capture-card-more.js").read_text(encoding="utf-8")


def test_the_second_file_is_lazy_and_loaded_by_the_card():
    assert "capture-card-more.js" in LAZY_PIECES
    assert "capture-card-more.js" not in {p.name for p in app_js_files()}
    assert "/js/capture-card-more.js" in _function_body(CARD, "openCaptureCard")


def test_the_dots_are_the_category_swatch_picker_over_eight_of_its_twelve_keys():
    sync = _function_body(MORE, "syncCaptureExtras")
    assert "swatchPicker(" in sync and "CATEGORY_PALETTE[key]" in sync
    keys = re.search(r"CAPTURE_COLOURS = \[([^\]]+)\]", MORE).group(1)
    from tessellate.api.schemas import NOTE_COLOURS

    for key in re.findall(r'"(\w+)"', keys):
        assert key in NOTE_COLOURS


def test_the_bell_offers_the_reminder_setters_own_quick_times_and_no_reminder():
    for key in ("30m", "1h", "3h", "tonight", "tomorrow", "tomorrowpm", "weekend", "nextweek"):
        assert f'"{key}"' in MORE
        assert f'case "{key}"' in (JS / "shell-reminders.js").read_text(encoding="utf-8")
    assert "presetDate(" in MORE and "labelledMenu(" in MORE and "No reminder" in MORE


def test_a_save_sends_the_colour_and_tags_and_puts_the_reminder_on_the_saved_note():
    save = _function_body(CARD, "saveCaptureCard")
    assert "body.colour" in save and "captureTagList(" in save
    done = _function_body(CARD, "finishCaptureSave")
    assert "quickNoteReminder(" in done and "announceSavedNote(" in done


def test_tags_take_hashes_spaces_and_commas():
    assert "tag.replace(/^#+/" in _function_body(CARD, "captureTagList")


def test_a_note_card_is_tinted_by_its_colour_with_the_swatch_hex_from_the_one_palette():
    cards = (JS / "note-cards.js").read_text(encoding="utf-8")
    assert "CATEGORY_PALETTE[entry.colour]" in cards and '"--swatch"' in cards
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert '#entry-list li[data-colour]' in css and "color-mix(in srgb, var(--swatch) 10%" in css


# --- step 4: pictures and Draw ------------------------------------------------------


def test_the_bar_has_a_picture_button_after_the_input_that_opens_the_picker():
    row = INDEX[INDEX.index('id="capture-bar-row"') :]
    assert row.index('id="capture-bar-input"') < row.index('id="capture-bar-picture"')
    button = re.search(r'<button[^>]*id="capture-bar-picture"[^>]*>', row).group(0)
    assert 'aria-label="Add pictures' in button and 'title="Add pictures"' in button
    # the picker opens from the lazy file, on the click that fetched it: no boot bytes
    notes = (JS / "notes-list.js").read_text(encoding="utf-8")
    assert "openCaptureCard(event.target, event.type)" in notes
    assert 'from?.closest?.("#capture-bar-picture")' in _function_body(CARD, "openCaptureCard")


def test_pictures_are_uploaded_on_save_and_written_as_the_markdown_the_editor_writes():
    assert "/media/upload" in _function_body(MORE, "uploadCapturePictures")
    assert "![" in _function_body(MORE, "uploadCapturePictures")
    save = _function_body(CARD, "saveCaptureCard")
    assert "uploadCapturePictures()" in save and "captureCard.pictures.length" in save
    # a picture alone is a note; a failed upload keeps the card and the words
    assert "!text && !captureCard.pictures.length" in save
    assert "catch (error)" in save


def test_an_uploaded_picture_is_not_uploaded_twice_when_a_retry_follows_a_failure():
    assert "picture.uploaded" in _function_body(MORE, "uploadCapturePictures")


def test_thumbnails_have_a_remove_button_and_images_only_are_taken():
    assert "Remove " in _function_body(MORE, "captureThumb")
    add = _function_body(MORE, "addCapturePictures")
    assert 'startsWith("image/")' in add and "CAPTURE_PICTURE_LIMIT" in add
    assert "URL.revokeObjectURL" in _function_body(MORE, "removeCapturePicture")


def test_draw_opens_the_sketch_pad_with_a_host_that_adds_the_picture_to_the_card():
    assert 'data-cc": "draw"' in _function_body(MORE, "mountCapturePictures") or '"draw"' in MORE
    host = _function_body(MORE, "captureSketchHost")
    assert "sketchHost()" in host and "saveLabel" in host and "addCaptureSketch" in host
    assert "openSketch({ host:" in _function_body(MORE, "openCaptureDraw")
    media = (JS / "media.js").read_text(encoding="utf-8")
    assert "options.host || sketchHost()" in media
    pad = (JS / "sketch-pad.js").read_text(encoding="utf-8")
    assert "S.host.saveLabel" in pad and 'saveLabel: "Save as note"' in pad


def test_a_reset_clears_the_pictures():
    reset = _function_body(CARD, "resetCaptureCard")
    assert "captureCard.pictures" in reset and "URL.revokeObjectURL" in reset
