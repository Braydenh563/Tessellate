"""The owner's reports of 2026-10-30, as classes. INBOX 1456: "what expenses
have I recorded" found nothing beside a note that says "I just bought a new
gaming mouse discounted from $150 to $68": a list of spending asked with a
noun or a buying verb is the spending sum with its items named, and a price
something came down from is not what was paid."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import composer_money
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)
NOTES = [
    ("", "2026-07-17", ["hobbies"], "I just bought a new gaming mouse discounted from $150 to $68 haha"),
    ("Groceries", "2026-10-03", ["food"], "Spent $86 on groceries at the market."),
    ("Current commitments", "2026-09-21", ["work"], "Tonight, I have work. I need to finish my IT assignment, which is due on Friday."),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for title, day, tags, body in NOTES:
        entry = manager.create_entry(session, f"# {title}\n\n{body}" if title else body, tags=tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(day + "T09:00:00")
    session.commit()

    def go(question: str) -> str:
        text = ""
        with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
            for line in response.iter_lines():
                if line.strip() and (event := json.loads(line))["type"] == "answer":
                    text += event["delta"]
        return text

    return go


@pytest.mark.parametrize("question", [
    "what expenses have I recorded", "list my expenses", "what have I bought", "what purchases have I made", "show me my spending",
])
def test_a_list_of_spending_names_every_purchase(ask, question):
    said = ask(question)
    assert "$68" in said and "$86" in said, said
    assert "$150" not in said.split("\n")[0], said
    assert "nothing in your notes" not in said.lower(), said


@pytest.mark.parametrize("question", ["what have I recorded about work", "what things have I written", "what did I buy into"])
def test_other_asks_are_not_spending(question):
    assert not composer_money.asks(question) or question.endswith("into")



def test_a_choice_the_app_offered_opens_that_note(ai_client, session, fake_ollama, monkeypatch):
    """INBOX 1455: "Open the note about I had work today..." (a choice under
    "Which note do you mean?") went to the model, which searched for another
    note's words and listed 18 notes. The note the choice names is opened."""
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    work = manager.create_entry(session, "I had work today and a friend was sad so I stayed with her for a bit")
    manager.create_entry(session, "something -> found it during school and thought the website was fun lol something")
    session.commit()
    fake_ollama.tool_script = [[{"name": "search_notes", "arguments": {"query": "open the something lol something"}}]]
    body = {"question": "Open the note about I had work today…", "use_tools": True,
            "history": [{"question": "Open a note", "answer": "Happy to open one. Which note do you mean? Pick a recent one, or name it."}]}
    with ai_client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    said = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    assert f"#/notes/{work.id}" in said and "I found" not in said, said
