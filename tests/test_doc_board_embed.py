"""A board embedded in a document is edited from it (DOCUMENTS_PLAN 26, gap row 10): "Edit here" lends the whiteboard's one view
to a panel over the document. Static checks of the wiring; the behaviour was driven in the browser (HISTORY, "F1 run 2")."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"


def read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


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
