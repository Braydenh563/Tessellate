"""The "Ask Atlas" offer is never a two-line capsule (INBOX 464 (16)).

At 390 Chat's offer was a 320x46 pill holding two lines ("Ask Atlas: What
can Atlas change in my notebook?") and the Notes empty state's 332x46. On a
phone the offer takes `--radius-md`, which holds one line or two, and Chat's
says its question shorter (one line, 214x44). Desktop keeps the pill.
"""
import re
from pathlib import Path
from tests._app_js import with_pieces

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
CHAT = with_pieces("chat.js")


def test_on_a_phone_the_offer_takes_a_buttons_corner():
    m = re.search(
        r"@media \(max-width: 599\.98px\) \{\s*\.help-atlas > \.atlas-suggest \{([^}]*)\}", CSS
    )
    assert m and "border-radius: var(--radius-md)" in m.group(1)


def test_chats_offer_names_atlas_once():
    assert "Ask Atlas: What can Atlas" not in CHAT
    assert 'atlasSuggestion("What can Atlas change in my notebook?", "Ask Atlas what it can change")' in CHAT
