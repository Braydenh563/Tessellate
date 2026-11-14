"""A question asked from a suggested next question says where it came from (INBOX 490).

The owner: "I feel like there should be hyperlinked bread crumbs or a file tree
sort of thing for if a suggested follow suggested question is used." Chat
draws a trail of the questions a chain of suggested questions came from above the question,
each a link that scrolls to its turn and lights it; Ask draws the same trail
above its answer, each crumb opening that earlier answer in place. Driven in
Chromium by the session's `trail490.js`; this is the server half (the link is
saved with the turn, so the trail survives reopening the chat) and the cheap
half of the client.
"""

from __future__ import annotations

from pathlib import Path
from tests._app_js import with_pieces

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_the_turn_keeps_which_question_it_followed(client):
    created = client.post("/conversations", json={"question": "What is moss?", "answer": "A plant."}).json()
    client.post(
        f"/conversations/{created['id']}/turns",
        json={"question": "Where does moss grow?", "answer": "Damp places.", "followup_of": "What is moss?"},
    )
    client.post(f"/conversations/{created['id']}/turns", json={"question": "Typed by hand", "answer": "ok"})
    messages = client.get(f"/conversations/{created['id']}").json()["messages"]
    assert messages[2] == {**messages[2], "role": "user", "followup_of": "What is moss?"}
    # A question typed by hand carries nothing, not an empty key.
    assert "followup_of" not in messages[0] and "followup_of" not in messages[4]
    # Bounded: the link is a question, not a document.
    too_long = client.post(
        f"/conversations/{created['id']}/turns",
        json={"question": "q", "answer": "a", "followup_of": "x" * 5000},
    )
    assert too_long.status_code == 422


def test_chat_sends_and_redraws_the_link():
    attach = with_pieces("chat-attach.js")
    selects = (JS / "sheets-selects.js").read_text(encoding="utf-8")
    # A chip sends its question with the one it was offered under.
    assert "sendChatMessage(pick, { followupOf:" in attach
    assert "followup_of: followupOf" in attach
    # The reopened chat draws the same trail through the same function.
    assert "markFollowup(" in selects and "message.followup_of" in selects


def test_ask_keeps_the_chain_its_chips_started():
    ask = with_pieces("capture-ask.js")
    assert "askTrailPending = [...askTrail, conversation.length - 1]" in (JS / "ask-compose.js").read_text(encoding="utf-8")
    assert "renderAskTrail()" in ask
