"""WORLD_CLASS_PLAN, "Placed from INBOX, 2026-09-09" (section 8, row 31).

What was left of the list: 99 (b) a saved chat reopening where it was left,
(c) the AI dot's last-answer line, (d) Paste as note; 92's suggested-link row;
22's Packages alignment; 261's vault re-key with no way to press it.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests import _js_scope
from tests._app_js import app_js_text
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
APP = app_js_text()
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
JS = ROOT / "frontend" / "js"


def _body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_paste_as_note_is_a_chord_left_to_the_browser_in_a_text_box():
    wiring = (JS / "settings-wiring.js").read_text(encoding="utf-8")
    assert 'pasteNote: { keys: "Ctrl+Shift+V"' in wiring
    assert 'id === "pasteNote") && inTextField) continue;' in wiring
    paste = _body(_js_scope.unwrapped((JS / "quick-note.js").read_text(encoding="utf-8")), "pasteClipboardAsNote")
    assert "navigator.clipboard.readText()" in paste and "createNoteSafely(" in paste
    assert "pushUndo(" in paste
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8") + (JS / "app-features.js").read_text(encoding="utf-8")
    assert 'chord: "pasteNote"' in panes


def test_a_saved_chat_reopens_where_it_was_left():
    assert "restoreChatPosition(full.id)" in _body(APP, "openConversation")
    note = _body(APP, "noteChatPosition")
    assert "CHAT_POSITIONS_KEY" in note and "delete map[id]" in note


def test_the_ai_dot_says_how_the_last_answer_went():
    line = _body(APP, "lastAnswerLine")
    assert "% of its window" in line and "Last answer:" in line
    assert "lastAnswerLine()" in _body(APP, "renderAiPill")
    assert "lastAnswerFacts = {" in APP


def test_a_suggested_link_is_two_chips_a_bar_and_a_reason_on_request():
    inbox = _js_scope.unwrapped((JS / "suggestions-inbox.js").read_text(encoding="utf-8"))
    row = _body(inbox, "inboxLinkRow")
    assert "link-suggestion-note" in row and "ph-arrows-left-right" in row
    assert "Add a reason" in row and 'reason.classList.add("hidden")' in row
    assert "inboxScoreBar(" in row
    assert "Link all above 70%" in inbox


def test_the_vault_rekey_has_a_button():
    assert 'id="account-rekey"' in HTML and 'id="account-rekey-password"' not in HTML
    assert 'data-help-for="rekey-help"' in HTML
    controls = unwrapped((JS / "settings-controls.js").read_text(encoding="utf-8"))
    assert '"/auth/rotate-vault-key"' in controls
    #: The password on the lock card's prompt, not a second password field.
    assert "askPasswordPrompt({" in controls[controls.index('$("account-rekey")') :][:1200]


def test_a_package_name_line_is_as_tall_as_its_buttons():
    css = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    rule = re.search(r"\.extras-row \.entry-title \{[^}]*\}", css).group(0)
    assert "min-height: var(--control-h-lg)" in rule
