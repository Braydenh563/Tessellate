"""A board embedded in a document is edited from it (DOCUMENTS_PLAN 26, gap row 10): "Edit here" lends the whiteboard's one view
to a panel over the document. Static checks of the wiring; the behaviour was driven in the browser (HISTORY, "F1 run 2")."""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"


def read(name: str) -> str:
    return frontend_text(name) if name.startswith("whiteboard") else (JS / name).read_text(encoding="utf-8")


def test_both_views_offer_edit_here_and_ask_for_the_lazy_panel() -> None:
    embeds = read("documents-embeds.js")
    # Live draws the card itself (docEmbedNode); Read's card is markdown.js's, so the button is added after it by renderDocPreview.
    assert "boardEditButton(target.entry.id" in embeds
    assert "docEmbedFill.editButtons = " in embeds and "docEmbedFill.editButtons(preview)" in read("documents.js")
    assert 'ensureModule("docBoard")' in embeds
    assert 'docBoard: ["/js/documents-board.js"]' in read("lazy-entries.js")


def test_the_whiteboard_side_is_two_small_hooks() -> None:
    wb = read("whiteboard.js")
    # The Library page is not switched to when the caller has already put the view where the board is wanted.
    assert "async function openWhiteboardBoard(boardId, opts = null)" in wb and "if (!opts?.stay) {" in wb
    # Leaving to the board list is first offered to whoever lent the view.
    assert 'new CustomEvent("wb-leave", { cancelable: true })' in wb


def test_the_panel_puts_the_view_back_and_names_no_whiteboard_global_bare() -> None:
    panel = read("documents-board.js")
    assert "was.home.insertBefore(was.view, was.next)" in panel and 'was.view.classList.toggle("hidden", was.hidden)' in panel
    # A lazy file may not name a global another bundle defines: the whiteboard's functions are reached through window.
    code = "\n".join(line for line in panel.splitlines() if not line.lstrip().startswith("//"))
    for name in ("openWhiteboardBoard", "wbShowBoardsLanding", "wbCancelBoardTimers", "loadMapBoardIndex"):
        assert f"window.{name}" in code
        assert not re.search(rf"(?<!window\.)\b{name}\b", code), name


def test_the_guide_has_a_topic_and_a_lead_for_a_board_in_a_document() -> None:
    from tessellate.ai import help_chat, help_leads

    topics = {t["id"]: t for t in help_chat.HELP_TOPICS}
    assert "document-board" in topics and len(topics["document-board"]["body"]) < 1900
    assert "document-board" in help_leads.TOPIC_LEADS
    assert "Edit here" in topics["document-board"]["body"]


def test_the_panel_closes_on_the_escape_the_board_did_not_take_and_returns_the_focus() -> None:
    panel = read("documents-board.js")
    # The board's state is read before its handlers run (capture); the close is on window, after every document handler.
    assert 'document.addEventListener("keydown", (event) => {\n    if (open && event.key === "Escape") boardTookEscape' in panel
    assert "}, true);" in panel and 'window.addEventListener("keydown"' in panel
    assert "event.defaultPrevented" in panel and "activeOverlay() !== open.overlay" in panel
    for taken in ("wb-fullscreen", "wb-presenting", ".action-menu:not(.hidden)", ".wb-ctx-menu:not(.hidden)", "contenteditable"):
        assert taken in panel, taken
    wb = read("whiteboard.js")
    wants = wb.split("wbShowBoardsLanding.wantsEscape = () => {")[1].split("\n};")[0]
    for state in ("wbSelectedItem", "wbMultiSelection.size", "wbPresent", "window.currentTool", "wbCtxMenuEl", "wb-search-bar", ".wb-marquee"):
        assert state in wants, state
    # Full screen inside the panel is left by the board's own Escape: its overlay is not "a dialog over the board".
    assert '.modal-overlay:not(.hidden):not(.doc-board-overlay), .lightbox' in wb
    # The opener is found again after the redraw replaced it: by board id and place.
    assert "edit.dataset.boardId = String(id)" in read("documents-embeds.js")
    assert ".doc-embed-board-edit[data-board-id=" in panel and "was.nth" in panel


def test_closing_leaves_the_library_as_it_was() -> None:
    panel = read("documents-board.js")
    # The board the Library had open is loaded again with its camera; a Library on its list is put back on the list.
    assert 'window.currentBoardId != null ? window.currentBoardId : null' in panel
    assert "window.openWhiteboardBoard(was.libraryBoard, { stay: true, restore: true })" in panel
    assert "window.wbShowBoardsLanding?.()" in panel and "window.wbLeaveFullscreen?.()" in panel
    wb = read("whiteboard.js")
    assert "function wbRestoreOrFrameBoard(boardId, restore = false)" in wb
    assert "if (saved && restore) {" in wb
    assert "wbRestoreOrFrameBoard(boardId ?? null, Boolean(opts?.restore))" in wb
    # A board looked at in the panel is not a place the person went: nothing is added to the back history.
    assert 'typeof recordTabVisit === "function" && !opts?.stay' in wb


def test_full_screen_in_the_panel_fills_the_window_and_the_print_rules_hide_the_button() -> None:
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".doc-board-card #library-view-whiteboard.wb-fullscreen {\n  position: relative;" in css
    full = css.split(".doc-board-overlay:has(.wb-fullscreen) {")[1].split("}")[0]
    assert "padding: 0" in full
    card = css.split(".doc-board-overlay:has(.wb-fullscreen) .doc-board-card {")[1].split("}")[0]
    assert "width: 100vw" in card and "max-width: none" in card and "margin: 0" in card
    assert "@media print {\n  .doc-embed-board-edit {\n    display: none;" in css
    assert ".doc-board-closing {\n  visibility: hidden;" in css


def test_a_plot_its_key_and_a_table_of_notes_print_in_the_sheets_ink_and_inside_its_width() -> None:
    graph = (ROOT / "frontend" / "css" / "doc-graph-lazy.css").read_text(encoding="utf-8")
    base = (ROOT / "frontend" / "css" / "doc-base-lazy.css").read_text(encoding="utf-8")
    # Paper is white whatever the theme: the light values of the ink, the grid and the ground, so a dark theme prints legibly.
    for css, block in ((graph, ".md-graph {\n    --ink: black;"), (base, ".md-base {\n    --ink: black;")):
        assert block in css and "--card: white;" in css and "--muted: dimgray;" in css
    # A table that cannot scroll wraps (a long word breaks) and, on a small sheet, shares the width.
    assert "overflow-wrap: break-word;" in base.split("@media print {")[1]
    small = base.split("@media print and (max-width: 599.98px) {")[1]
    assert "table-layout: fixed;" in small and "overflow-wrap: anywhere;" in small
