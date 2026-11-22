"""Which turns "Ask again" offers back (routes_chat.py's `/chat/recent`).

Reported directly: *"tasks that I have put in the agent show in the 'ask'
again section, the things that I will ask the agent are different to what I
would ask if searching in my notebook."* Every turn used to write the same
`queried`/`chat` audit row, so an instruction the agent had already carried
out came back as a chip inviting you to run it again.

The rule the report gave, in the user's words: *"if I was in the chat and
using the 'ask' mode, then those queries should count, but only those, and my
previous requests in the 'ask' subtab in notes should be registered."*
"""

from __future__ import annotations

import json

from tessellate.core.database import AuditLog
from tessellate.entry import manager


def _stream(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as r:
        for line in r.iter_lines():
            if line.strip():
                json.loads(line)


def test_notes_ask_box_is_offered_again(ai_client, fake_ollama, session):
    manager.create_entry(session, "The beans need netting next week")
    session.commit()
    fake_ollama.librarian_reply = "You wrote about netting the beans."
    _stream(ai_client, "what did I write about beans", notes_only=True)

    assert "what did I write about beans" in ai_client.get("/chat/recent").json()


def test_chat_in_ask_mode_is_offered_again(ai_client, fake_ollama, session):
    """Tools off is what the Chat tab's "Ask the Librarian" button sends."""
    manager.create_entry(session, "The beans need netting next week")
    session.commit()
    fake_ollama.librarian_reply = "You wrote about netting the beans."
    _stream(ai_client, "which notes mention beans", use_tools=False)

    assert "which notes mention beans" in ai_client.get("/chat/recent").json()


def test_a_request_to_the_agent_is_not_offered_again(ai_client, fake_ollama, session):
    """Request mode and the Ctrl+Shift+A palette both send `use_tools`."""
    manager.create_entry(session, "The beans need netting next week")
    session.commit()
    fake_ollama.librarian_reply = "Done."
    _stream(ai_client, "tag every note about beans", use_tools=True)

    assert ai_client.get("/chat/recent").json() == []


def test_the_request_is_still_in_the_audit_log(ai_client, fake_ollama, session):
    """Narrowing the chip row must not lose the record of what happened, 
    the log is a history, not a suggestion list."""
    fake_ollama.librarian_reply = "Done."
    _stream(ai_client, "tag every note about beans", use_tools=True)

    rows = session.query(AuditLog).filter(AuditLog.action == "queried").all()
    assert [r.entity_type for r in rows] == ["agent"]
    assert rows[0].detail == "tag every note about beans"


def test_the_two_surfaces_do_not_mix(ai_client, fake_ollama, session):
    manager.create_entry(session, "The beans need netting next week")
    session.commit()
    fake_ollama.librarian_reply = "ok"
    _stream(ai_client, "delete the bean note", use_tools=True)
    _stream(ai_client, "what did I write about beans", notes_only=True)

    recent = ai_client.get("/chat/recent").json()
    assert "what did I write about beans" in recent
    assert "delete the bean note" not in recent


def _asked(session, question):
    from tessellate.api.chat_recent import ASK_SURFACE

    session.add(AuditLog(action="queried", entity_type=ASK_SURFACE, detail=question))
    session.commit()


def test_clearing_the_history_clears_ask_again(client, session):
    """The owner, 2026-10-10: "There's no way to clear your ask history"
    (with the Ask again row under the box). Clear history now empties that
    row too; the audit log keeps every question, and a question asked after
    the clear comes back as usual."""
    _asked(session, "what about beans")
    _asked(session, "what about peas")
    assert client.get("/chat/recent").json() == ["what about peas", "what about beans"]
    cleared = client.delete("/ask-history")
    assert cleared.status_code == 200
    assert client.get("/chat/recent").json() == []
    assert session.query(AuditLog).filter_by(action="queried").count() == 2
    _asked(session, "what about leeks")
    assert client.get("/chat/recent").json() == ["what about leeks"]


def test_one_question_can_be_forgotten(client, session):
    """"no way to ... delete individual records??": one chip goes, the
    others stay, and asking it again brings it back."""
    _asked(session, "what about beans")
    _asked(session, "what about peas")
    response = client.delete("/chat/recent", params={"question": "what about beans"})
    assert response.status_code == 200
    assert client.get("/chat/recent").json() == ["what about peas"]
    _asked(session, "what about beans")
    assert client.get("/chat/recent").json() == ["what about beans", "what about peas"]
