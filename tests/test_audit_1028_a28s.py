"""Audit 1028 rows fixed by agent a28s (S62, S91, S92, U38, U48, B32, B28, B34, D53, K35).

Each test pins the cause of one row in the source, so the fix cannot be undone
without a failing line that names the row. The browser behaviour of each is
measured in the sweep named in its CHANGELOG line.
"""

from __future__ import annotations

from tests._app_js import JS_DIR, app_js_text, frontend_text


def _js(name: str) -> str:
    """A lazy bundle's file, which `app_js_text()` (the boot scripts) does not hold."""
    return frontend_text(name) if name.startswith("whiteboard") or name == "documents.js" else (JS_DIR / name).read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    at = text.index(start)
    return text[at : text.index(end, at + 1)]


def test_s62_editor_palette_with_no_match_offers_a_notes_search():
    """S62: ">" and words that match no editor command left an empty list. A row
    now carries them to Find anything, notes only."""
    block = _between(app_js_text(), 'if (lowered.startsWith(">")) {', "const base = paletteBase(")
    assert "Search notes for" in block
    assert 'openFinder(typed, { kind: "note" })' in block


def test_s91_the_window_title_follows_the_view_and_keeps_the_unread_count():
    """S91 was already fixed when it was swept: the router paints the view into
    the window title and `paintTitle` keeps the unread count in front of it."""
    text = app_js_text()
    assert "setTitleView([item, view].filter(Boolean).join(\" · \"))" in text
    assert "document.title = pageTitle.count > 0 ? `(${pageTitle.count}) ${base}` : base;" in text


def test_u38_a_document_title_another_has_is_said_once_and_left_as_typed():
    """U38: the save says so in a toast, once per document and name; no suffix."""
    block = _between(_js("documents.js"), "async function docSaveOnce(", "} catch (error) {")
    assert "Another document is called" in block
    assert "said.has(" in block and "said.add(" in block
    assert '" (2)"' not in block


def test_u48_the_export_dialog_opens_on_the_whole_board_when_nothing_is_selected():
    """U48: "On screen" was the first export's scope and put "(view)" in its file name."""
    block = _between(_js("whiteboard.js"), "function wbExportBoard(", "const overlay = ")  # takes { branch } since L267
    assert 'let scope = hasSelection ? "selection" : "whole";' in block


def test_b32_the_maps_timers_and_frames_are_kept_and_cancelled_on_a_board_switch():
    """B32: whiteboard-map.js had two frames and two timers nothing could cancel."""
    source = _js("whiteboard-map.js")
    assert "setTimeout(" not in source.replace("else id = setTimeout(run);", "")
    assert source.count("requestAnimationFrame(") == 1  # the one inside wbMapCache.defer
    assert "cancelAnimationFrame(id)" in source and "clearTimeout(id)" in source
    assert "wbMapCache.cancelAll();" in _between(_js("whiteboard.js"), "function wbCancelBoardTimers()", "return wbFlushNudge();")


def test_b28_a_picture_pasted_as_markup_or_an_address_is_placed_or_refused_with_a_reason():
    """B28: the board's paste took files and text only, and no picture was checked
    against the upload cap before the request."""
    source = _js("whiteboard.js")
    assert "const wbPictureCap = 50 * 1024 * 1024;" in source
    assert "if (file.size > wbPictureCap) return wbPictureTooBig();" in source
    handler = _between(source, 'document.addEventListener("paste", (e) => {', 'document.addEventListener("copy"')
    assert "wbPastedPictureAddress(data, html)" in handler
    assert handler.index("wbPastedPictureAddress(") < handler.index('getData("text/plain")')
    helper = _between(source, "function wbPastedPictureAddress(", "function wbPlacePastedAddress(")
    assert "text/uri-list" in helper and "img[src]" in helper
    place = _between(source, "async function wbPlacePastedAddress(", "async function wbPlaceUploadedImage(")
    assert "works offline" in place  # a web address is refused with the reason, not dropped


def test_b34_an_empty_board_keeps_one_line_after_its_card_is_put_away():
    """B34: closing or turning off the card left a bare canvas. `#wb-empty-cue` is the
    `p.muted.empty-line` recipe, shown when the card is hidden on a board holding nothing."""
    html = (JS_DIR.parent / "index.html").read_text(encoding="utf-8")
    assert 'id="wb-empty-cue" class="muted empty-line wb-empty-cue hidden"' in html
    source = _js("whiteboard.js")
    render = _between(source, "const wbBoardHolds = ", "// Render Sketches (SVG)")
    assert '"wb-empty-cue"' in render and "!(wbHintHidden && !wbIsMap() && wbBoardHolds === 0)" in render
    for button in ("wb-empty-hint-close", "wb-empty-hint-dismiss"):
        handler = _between(source, f'$("{button}")?.addEventListener', "});")
        assert 'wb-empty-cue' in handler, button
    css = (JS_DIR.parent / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert "pointer-events: none" in _between(css, ".wb-empty-cue {", "}")


def test_d53_run_output_cut_at_4000_characters_says_so():
    """D53: a console row and a failed test's reason were sliced at 4,000 characters in silence."""
    source = _js("documents-code.js")
    cut = "`${String(text).slice(0, 4000)}\\nOutput cut at 4,000 characters.`"
    assert source.count(cut) == 2
    assert ".textContent = String(text).slice(0, 4000);" not in source


def test_s92_a_loaded_or_filtered_list_says_its_count_through_the_one_live_region():
    """S92: Notes and the Library announce their count, settled and once, through
    `announce` (the page's `#live-region`), not a region each."""
    text = app_js_text()
    assert 'announce(`${scope}: ${nounCount(visible.length, "note")}`, { settle: 600, once: true })' in text
    assert 'announce(`Library: ${nounCount(items.length, "item")}`, { settle: 600, once: true })' in _js("library.js")
    head = _between(text, "function announce(message,", "// Jump to an entry")
    assert "settle" in head and "once" in head
