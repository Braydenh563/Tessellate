"""L169 (E44): `chatSendTurn` is a short driver over named stages, not one 1,190-line function.

Measured 2026-11-14: 29 lines, its stages on `chatSendTurn.stage`."""

import re
from pathlib import Path

JS = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "chat-turn.js").read_text(encoding="utf-8")


def test_chat_send_turn_stays_a_short_driver():
    start = JS.index("async function chatSendTurn(")
    end = JS.index("\n}\n", start) + 3
    assert JS[start:end].count("\n") <= 60
    assert len(re.findall(r"^  (?:async )?\w+\(\w*\) \{$", JS[JS.index("chatSendTurn.stage = {"):], re.M)) >= 5
