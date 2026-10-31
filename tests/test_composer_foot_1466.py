"""INBOX 1466, the rest: under a composed Ask answer (no model) only "Why this
answer" showed. The prose offer ("Next, I can open ...") is now the follow-up
chips, and the notes linked to the ones it cited fill the related row. A model
answer is untouched (CHAT_PLAN decision 75: the composer never stands in)."""

from __future__ import annotations

import pytest

from tessellate.core.database import Entry, EntryLink
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

GYM = "Gym plan: I lift on Monday and Thursday at 6pm.\n\nNeed to buy new gloves before next week."
COACH = "Coach says my bench form needs work before the next block"
SOUP = "Recipe: lentil soup. Simmer for 25 minutes."

OFFER = ("Next, I can", "Want me to open", "I can summarise", "Say the word", "ask me what is still open")


@pytest.fixture
def notebook(session):
    gym = manager.create_entry(session, GYM)
    coach = manager.create_entry(session, COACH)
    soup = manager.create_entry(session, SOUP)
    session.add(EntryLink(source_entry_id=coach.id, target_entry_id=gym.id))
    session.commit()
    return {"gym": gym.id, "coach": coach.id, "soup": soup.id}


def _asked(client, question, **body):
    return _ask(client, question, use_tools=False, notes_only=True, answer_from="notes", **body)


def test_the_prose_offer_is_the_chips_not_both(client, notebook):
    out = _asked(client, "what is left in Gym plan")
    chips = out["grounding"][0]["next"]
    assert any(c.startswith("Open “") for c in chips), chips
    assert any(c.startswith("What is left in “") and c.endswith("?") for c in chips), chips
    assert not any(phrase in out["text"] for phrase in OFFER), out["text"]


def test_an_answer_that_already_asks_gets_no_closing_chips(client, notebook):
    out = _asked(client, "what is left in Gym plan", mode="quick")
    assert not any(c.startswith("Open “") for c in out["grounding"][0]["next"])


def test_a_linked_note_is_related_and_a_cited_one_is_not(client, notebook):
    out = _asked(client, "what is my gym plan")
    (event,) = out["related"]
    assert event["items"] == [{"kind": "note", "id": notebook["coach"], "label": COACH}]


def test_nothing_linked_means_no_related_event(client, notebook):
    assert "related" not in _asked(client, "tell me about the lentil soup")


def test_a_deleted_linked_note_is_not_offered(client, session, notebook):
    manager.soft_delete_entry(session, session.get(Entry, notebook["coach"]))
    session.commit()
    assert "related" not in _asked(client, "what is my gym plan")


def test_a_running_model_answers_without_the_composers_foot(ai_client, fake_ollama, notebook):
    out = _ask(ai_client, "what is my gym plan", use_tools=False)
    assert "related" not in out
    assert fake_ollama.librarian_reply in out["text"]


def test_a_quoted_document_is_a_source_with_its_title(client, session):
    from tessellate.core.database import Document

    session.add(Document(title="Tax return checklist", content="Gather the P60. File the return by 31 January."))
    session.commit()
    row = _asked(client, "when do I file the tax return")["grounding"][0]["sentences"][0]
    assert (row["kind"], row["title"]) == ("document", "Tax return checklist")


def test_the_page_turns_a_quoted_document_into_a_source_card():
    from tests._app_js import app_js_text

    js = app_js_text()
    assert 'filter((g) => g.kind === "document")' in js
    assert 'source.kind === "note" || source.kind === "document"' in js
