"""Audit 1030 A20 to A34: the chat and Ask screens' small bugs, read from the source.

The behaviours were measured in the running app (see the audit rows); these
pin the lines that carry them, so a later edit cannot quietly drop one.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathlib import Path

from tessellate.api.routes_conversations import RenameBody


def app_js_text() -> str:
    """Every script, the lazy ones included: these rows touch both."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted((Path(__file__).resolve().parents[1] / "frontend/js").glob("*.js")))


def _body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : start + 3000]


def test_deleting_a_turn_recounts_the_header_a20():
    assert "renderChatTurnCount();" in _body(app_js_text(), "deleteChatTurn")


def test_a_reopened_chat_recounts_its_header_a20():
    js = (Path(__file__).resolve().parents[1] / "frontend/js/sheets-selects.js").read_text(encoding="utf-8")
    assert "renderChatTurnCount();\n  lazyScript(\"/js/chat-time.js\")" in js


def test_the_edit_hint_names_the_shortcut_a22():
    assert "Ctrl+Enter saves." in app_js_text()


def test_escape_closes_the_web_panel_and_the_model_panel_a23_a27():
    js = app_js_text()
    assert '$("web-panel").addEventListener("keydown"' in js
    assert "toggleWebPanel(false);\n  $(\"web-search-toggle\").focus();" in js
    assert 'panel._dismiss = dismiss;' in js
    assert "!chatDockMoreOpen()" in js


def test_a_copied_answer_writes_citations_in_brackets_a21():
    js = app_js_text()
    assert "function bodyTextWithCitations(" in js
    assert js.count("bodyTextWithCitations(") >= 3


def test_a_long_ask_question_never_asks_the_chart_route_a26():
    assert "question.length <= 500" in app_js_text()


def test_an_ask_history_search_with_no_match_has_its_own_line_a29():
    assert "No saved question matches." in app_js_text()


def test_chat_pin_rename_and_archive_offer_undo_on_the_toast_a32():
    undo = (Path(__file__).resolve().parents[1] / "frontend/js/chat-undo.js").read_text(encoding="utf-8")
    for name in ("chatTitleUndo", "chatPinUndo", "chatArchiveUndo"):
        assert "offerUndo(" in _body(undo, name), name
    frontend = Path(__file__).resolve().parents[1] / "frontend/js"
    assert 'toast("Archived.");' not in (frontend / "sheets-selects.js").read_text(encoding="utf-8")


def test_a_rename_is_bounded_and_a_blank_one_says_the_title_was_kept_a33():
    js = app_js_text()
    assert js.count("await promptTitle(") == 3
    assert ".maxLength = 120" in js and 'toast("Title kept.")' in js
    assert RenameBody(title="  Trip  ").title == "Trip"
    with pytest.raises(ValidationError):
        RenameBody(title="   ")


def test_naming_with_atlas_speaks_once_a34():
    js = app_js_text()
    assert "Kept the first question as the title." in js
    assert "Used the first question as the title.\"," not in js


def test_the_web_pill_says_where_a_search_runs_in_ask_mode_a6():
    assert "Atlas searches in Agent mode" in app_js_text()


def test_a_page_read_gives_up_in_seconds_a10():
    from tessellate.search import websearch

    assert websearch.READER_TIMEOUT[0] <= 4
