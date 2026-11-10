"""Parity, both ways (CHAT_PLAN decision 75; composer audit 2 "Parity" table and
the first audit's F14). Everything the composer says, a model up is handed as
facts; everything a model's tools can do, the composer can do with no model,
after the same Confirm. Each row: model off is the composer, model on is the
fake transport (what the prompt holds and which events come back; what a real
model writes is not verified). Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat, routes_insights
from tessellate.entry import manager
from tessellate.repo import reminders as reminder_repo

NOW = datetime(2026, 11, 10, 9, 0)

NOTES = [
    ("# Harbor launch plan\n\nShip the Harbor mobile app to the public on 14 December.", "Work", "2026-09-03T10:00:00"),
    ("# Wifi\n\nNetwork is Bluegum-5G. Router is in the hallway cupboard.", "Life", "2026-08-30T10:00:00"),
    ("Call mum on Sunday about christmas plans", "Personal", "2026-11-08T10:00:00"),
    ("feeling pretty tired today, slept badly", "Life", "2026-11-10T08:00:00"),
]
REMINDERS = [
    ("Pay phone bill", datetime(2026, 11, 10, 9, 0)),
    ("Take bins out", datetime(2026, 11, 10, 19, 0)),
    ("Book dentist", datetime(2026, 11, 14, 12, 0)),
]


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    for module in (routes_chat, chat_said, chat_turn, routes_insights):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


@pytest.fixture
def seeded(session):
    for content, cat, when in NOTES:
        entry = manager.create_entry(session, content, category_name=cat)
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
    for text, due in REMINDERS:
        reminder_repo.create(session, text=text, due_at=due, done=False)
    session.commit()
    return session


def stream(client, question: str, **body) -> dict:
    """Every event of one turn, grouped by type, with the answer text joined."""
    out: dict = {}
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                out.setdefault(event["type"], []).append(event)
    out["text"] = "".join(e["delta"] for e in out.get("answer", []))
    return out


def prompt_of(fake) -> str:
    """Everything the fake model was sent on its last turn."""
    rounds = [*fake.chat_calls[-1:], *fake.tool_rounds[-1:]]
    return "\n".join(str(m.get("content") or "") for messages in rounds for m in messages)


# --- the agenda ("what's on today") -------------------------------------------


@pytest.mark.parametrize("question", ["what's on today", "what have I got on today"])
def test_the_agenda_with_no_model_lists_the_days_reminders(client, seeded, question):
    said = stream(client, question)["text"]
    assert "Pay phone bill" in said and "Take bins out" in said, said


@pytest.mark.parametrize("question", ["what's on today", "what have I got on today"])
def test_the_agenda_with_a_model_is_handed_the_same_facts(ai_client, fake_ollama, seeded, question):
    stream(ai_client, question, use_tools=True)
    sent = prompt_of(fake_ollama)
    assert "Pay phone bill" in sent and "Take bins out" in sent, sent[-700:]


# --- the greeting ----------------------------------------------------------------


def test_a_hello_with_no_model_says_the_days_numbers(client, seeded):
    said = stream(client, "good morning")["text"]
    assert "reminder" in said and "feeling pretty tired today" in said, said


def test_a_hello_with_a_model_is_handed_the_same_numbers(ai_client, fake_ollama, seeded):
    stream(ai_client, "good morning")
    sent = prompt_of(fake_ollama)
    assert "reminder" in sent and "feeling pretty tired today" in sent, sent[-700:]


# --- chips under a model's answer (F14) -------------------------------------------


def _asks(out: dict) -> list[str]:
    return [a for e in out.get("offer", []) for a in e["offer"].get("asks", [])]


def test_a_composed_answer_that_cites_a_note_offers_to_open_it(client, seeded):
    out = stream(client, "when does the harbor app ship")
    chips = [c for e in out.get("grounding", []) for c in e.get("next", [])]
    assert any("Harbor launch plan" in c for c in chips), out["grounding"]


def test_a_model_answer_that_cites_a_note_offers_the_same_chip(ai_client, fake_ollama, seeded):
    fake_ollama.librarian_reply = "Ship the Harbor mobile app to the public on 14 December."
    out = stream(ai_client, "when does the harbor app ship", use_tools=False)
    assert any("Harbor launch plan" in a for a in _asks(out)), out


def test_a_model_hello_has_no_note_chip(ai_client, fake_ollama, seeded):
    assert _asks(stream(ai_client, "thanks")) == []


# --- the dashboard greeting ---------------------------------------------------------


def test_the_greeting_with_no_model_is_composed_from_the_notebook(client, seeded):
    body = client.get("/insights/greeting?block=morning").json()
    assert body["source"] == "composed" and body["greeting"]


def test_the_greeting_with_a_model_is_handed_the_composed_line(ai_client, fake_ollama, seeded):
    routes_insights._GREETING_FLIGHT.clear()
    composed = routes_insights._composed_greeting(seeded, routes_insights.deps.get_config(), "morning")[0]
    ai_client.get("/insights/greeting?block=morning")
    system = str(fake_ollama.chat_calls[-1][0]["content"])
    assert composed in system, system


# --- reads the model has tools for: the bin, earlier chats, export -------------------


@pytest.fixture
def binned(seeded):
    from tessellate.entry import manager as entries

    gone = entries.create_entry(seeded, "# Passport\n\nRenew in May.")
    seeded.commit()
    entries.soft_delete_entry(seeded, gone)
    seeded.commit()
    return gone


@pytest.fixture
def chats(seeded):
    import json as _json

    from tessellate.core.database import Conversation

    seeded.add(Conversation(title="Harbor launch chat", messages=_json.dumps([
        {"role": "user", "content": "when does the harbor app ship"}, {"role": "assistant", "content": "On 14 December."}])))
    seeded.commit()


@pytest.mark.parametrize("question", ["what's in my bin", "show my bin", "what did I delete"])
def test_the_bin_is_listed_with_no_model(client, binned, question):
    said = stream(client, question)["text"]
    assert "Passport" in said and "1 note" not in said and "in the bin" in said, said


def test_the_bin_is_handed_to_a_model_as_facts(ai_client, fake_ollama, binned):
    stream(ai_client, "what's in my bin", use_tools=True)
    assert "Passport" in prompt_of(fake_ollama)


@pytest.mark.parametrize("question", ["what did we talk about last time", "what did we discuss about harbor", "search my chats for harbor"])
def test_earlier_chats_are_read_with_no_model(client, chats, question):
    said = stream(client, question)["text"]
    assert "Harbor launch chat" in said and "when does the harbor app ship" in said, said


def test_earlier_chats_are_handed_to_a_model_as_facts(ai_client, fake_ollama, chats):
    stream(ai_client, "what did we talk about last time", use_tools=True)
    assert "Harbor launch chat" in prompt_of(fake_ollama)


def test_no_earlier_chat_is_said_plainly(client, seeded):
    assert "no earlier chat" in stream(client, "search my chats for zebra")["text"]


@pytest.mark.parametrize("question", ["export my notes", "how do I export my notes"])
def test_export_is_handed_off_to_settings_with_no_model(client, seeded, question):
    assert "#/settings/data" in stream(client, question)["text"]


def test_export_is_handed_to_a_model_as_a_fact(ai_client, fake_ollama, seeded):
    stream(ai_client, "export my notes", use_tools=True)
    assert "Import & export" in prompt_of(fake_ollama)


# --- the notebook's shape: notes on their own, how two notes are related ----------------


@pytest.fixture
def joined(seeded):
    from tessellate.core.database import EntryLink
    from tessellate.entry import manager as entries

    japan = entries.create_entry(seeded, "# Japan trip\n\nFlights booked for 12 March.")
    kyoto = entries.create_entry(seeded, "# Kyoto ideas\n\nFushimi Inari at sunrise.")
    seeded.add(EntryLink(source_entry_id=japan.id, target_entry_id=kyoto.id))
    seeded.commit()
    return seeded


@pytest.mark.parametrize("question", ["which notes are connected to nothing", "what are the clusters"])
def test_the_notes_on_their_own_are_listed_with_no_model(client, joined, question):
    said = stream(client, question)["text"]
    assert "Not linked to anything yet" in said and "On their own" in said, said


def test_the_shape_is_handed_to_a_model_as_facts(ai_client, fake_ollama, joined):
    stream(ai_client, "which notes are connected to nothing", use_tools=True)
    assert "Not linked to anything yet" in prompt_of(fake_ollama)


@pytest.mark.parametrize("question", ["how are japan trip and kyoto ideas related", "what links the japan trip and kyoto ideas"])
def test_how_two_notes_are_related_with_no_model(client, joined, question):
    said = stream(client, question)["text"]
    assert "linked directly" in said, said


def test_how_two_notes_are_related_handed_to_a_model_as_facts(ai_client, fake_ollama, joined):
    stream(ai_client, "how are japan trip and kyoto ideas related", use_tools=True)
    assert "linked directly" in prompt_of(fake_ollama)


# --- acts the model has a tool for: make a category, restore the last deleted note ----


def _card(out: dict) -> dict:
    return next(e for e in out.get("act", []) if not e.get("cancel") and not e.get("settle"))


def _names(session) -> set[str]:
    from sqlalchemy import select

    from tessellate.core.database import Category

    session.expire_all()
    return {c.name for c in session.scalars(select(Category))}


@pytest.mark.parametrize("sentence", ["create a category called Hobbies", "make a new category Hobbies", "add a category named Hobbies"])
def test_make_a_category_is_a_card_then_done_then_undone(client, seeded, sentence):
    out = stream(client, sentence)
    card = _card(out)
    assert "Hobbies" in card["label"] and "Hobbies" not in _names(seeded), out["text"]
    run = client.post("/chat/command/run", json={"steps": card["steps"], "consent_id": card["consent_id"]})
    assert run.status_code == 200 and "Hobbies" in _names(seeded), run.text
    assert client.post("/chat/command/run", json={"steps": run.json()["undo"]}).status_code == 200
    assert "Hobbies" not in _names(seeded)


def test_a_category_that_exists_is_said_not_made_again(client, seeded):
    assert "already a category" in stream(client, "create a category called Work")["text"]


@pytest.mark.parametrize("question", ["how do I make a category", "what is a category", "make a category of my cooking notes?"])
def test_a_question_about_categories_is_not_a_new_category(client, seeded, question):
    assert not stream(client, question).get("act")


def test_the_model_makes_the_same_category_only_after_consent():
    from tessellate.ai import act_registry, tools

    assert act_registry.ACT_TOOLS["create_category"] == "create_category" and act_registry.ACTS["create_category"].confirm
    assert tools.needs_confirm("create_category", {"name": "Hobbies"}) is True


def test_a_model_in_agent_mode_parks_make_a_category_for_confirm(ai_client, fake_ollama, seeded):
    fake_ollama.tool_script = [[{"name": "create_category", "arguments": {"name": "Hobbies"}}], []]
    out = stream(ai_client, "create a category called Hobbies", use_tools=True)
    assert "Hobbies" not in _names(seeded), out["text"]
    assert out.get("confirm") or out.get("act"), sorted(out)


def test_restore_the_last_deleted_note_is_a_card_for_the_newest(client, binned):
    out = stream(client, "restore the last deleted note")
    card = _card(out)
    assert "Passport" in card["label"], out["text"]
    assert card["steps"][0]["arguments"]["note_id"] == binned.id


def test_restore_with_an_empty_bin_says_so(client, seeded):
    assert "no notes I can restore" in stream(client, "restore the last deleted note")["text"]


# --- the weekly review and the Guide, model on (closed by G4 and G5; pinned here) ---


def test_the_weekly_review_with_a_model_is_handed_the_week(ai_client, fake_ollama, seeded):
    stream(ai_client, "weekly review", use_tools=True)
    sent = prompt_of(fake_ollama)
    assert "Harbor launch plan" in sent or "feeling pretty tired today" in sent, sent[-600:]


def test_the_guide_with_a_model_lifts_the_questions_it_suggests_as_chips(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "Pick a tag in the sidebar. Ask me “how do I merge tags” and I will show you."
    body = ai_client.post("/help/ask", json={"question": "how do I use tags"}).json()
    assert "How do I merge tags?" in body.get("asks", []), body


def test_the_guide_hello_is_composed_with_a_model_up(ai_client, fake_ollama):
    before = len(fake_ollama.chat_calls)
    body = ai_client.post("/help/ask", json={"question": "hello"}).json()
    assert len(fake_ollama.chat_calls) == before and body.get("greeting"), body
