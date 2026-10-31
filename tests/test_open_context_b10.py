"""The open tab as context (CHAT_PLAN B10): "Summarise this" sums up the
note that is open, else the category the sidebar filters to, through the
route with no model; with nothing open it says so rather than answering
with the newest notes; "summarise Travel" and "what's in Travel?" read the
whole category rather than what a keyword search finds.
"""

from __future__ import annotations

import json

import pytest

from tessellate.ai import composer_digest
from tessellate.entry import manager


def _turn(client, question: str, **extra) -> str:
    body = {"question": question, "history": [], "notes_only": True, "use_tools": False, "answer_from": "notes", **extra}
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.fixture
def notebook(session):
    trip = manager.create_entry(
        session,
        "Trip planning: flights to Lisbon on 3 May, 240 pounds. Hotel near Alfama booked for four nights. Still need travel insurance.",
        category_name="Travel",
    )
    manager.create_entry(session, "Packing list: adapter, sun cream, walking shoes.", category_name="Travel")
    gym = manager.create_entry(session, "Gym: squats at 80 kg.", category_name="Health")
    session.commit()
    return {"trip": trip.id, "gym": gym.id}


def test_summarise_this_sums_up_the_open_note_point_by_point(client, notebook):
    text = _turn(client, "Summarise this", open_note_id=notebook["trip"], open_category="Travel")
    #: INBOX 1441 moved the day out: "Summarise this" does not ask about
    #: time, so the note is named by its label and says no "of <date>".
    assert text.startswith("Your trip planning note, in Travel, in three points:"), text
    assert "- Flights to Lisbon on 3 May, 240 pounds.\n- Hotel near Alfama" in text
    assert "Packing" not in text and "squats" not in text


def test_a_one_point_note_is_one_sentence(client, notebook):
    text = _turn(client, "tl;dr", open_note_id=notebook["gym"])
    #: No "of <date>" for an untimed question (INBOX 1441).
    assert text.startswith("Your gym note, in Health, says one thing: squats at 80 kg."), text


def test_with_no_note_open_the_open_category_is_summed_up(client, notebook):
    text = _turn(client, "what's this about?", open_category="Travel")
    assert text.startswith("Two notes in Travel")
    assert "adapter" in text and "Lisbon" in text and "squats" not in text


def test_with_nothing_open_it_says_so(client, notebook):
    text = _turn(client, "Summarise this")
    assert text.startswith("Nothing is open to sum up.")
    assert "squats" not in text


@pytest.mark.parametrize("question", ["summarise Travel", "what's in Travel?", "what do I have in my travel notes?"])
def test_a_named_category_reads_all_its_notes(client, notebook, question):
    text = _turn(client, question)
    assert text.startswith("Two notes in Travel"), text
    assert "adapter" in text and "Lisbon" in text and "squats" not in text


def test_the_open_context_never_changes_another_question(client, notebook):
    text = _turn(client, "what have I saved about the gym?", open_note_id=notebook["trip"])
    assert "squats" in text and "Lisbon" not in text


@pytest.mark.parametrize("question", ["Summarise this", "summarise it please", "can you sum up this note?", "what is this about?", "TL;DR", "recap"])
def test_about_this_reads_the_phrasings(question):
    assert composer_digest.about_this(question)


@pytest.mark.parametrize("question", ["summarise my trip to Lisbon", "what is this week about?", "summarise the gym notes from May"])
def test_about_this_leaves_a_subject_alone(question):
    assert not composer_digest.about_this(question)


def test_with_a_model_up_the_model_summarises_the_open_note(ai_client, fake_ollama, session, monkeypatch):
    """Decision 75: the open note reaches the model as the note to answer
    from; the model writes the summary, and nothing open is the model's
    turn too (it searches), not the app's fixed line."""
    trip = manager.create_entry(session, "Trip planning: flights to Lisbon on 3 May, 240 pounds.", category_name="Travel")
    session.commit()
    seen: list[list[dict]] = []
    real = fake_ollama.chat_stream

    def recording(model, messages, mode=None):  # noqa: ANN001, ANN202
        seen.append(messages)
        return real(model, messages, mode)

    monkeypatch.setattr(fake_ollama, "chat_stream", recording)
    body = {"question": "Summarise this", "history": [], "use_tools": False, "open_note_id": trip.id}
    with ai_client.stream("POST", "/chat/stream", json=body) as response:
        text = "".join(json.loads(line).get("delta", "") for line in response.iter_lines() if line.strip() and json.loads(line).get("type") == "answer")
    assert seen, "the model was not asked"
    assert "Lisbon" in json.dumps(seen[-1])
    assert not text.startswith("Your trip planning note")
    with ai_client.stream("POST", "/chat/stream", json={"question": "Summarise this", "history": [], "use_tools": False}) as response:
        text = "".join(json.loads(line).get("delta", "") for line in response.iter_lines() if line.strip() and json.loads(line).get("type") == "answer")
    assert not text.startswith("Nothing is open to sum up.")
