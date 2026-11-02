"""Ask and Chat answer an app verb as an act, never a lookup; the same act
twice asks first; "show my reminders" lists them (audit 1029 C45, C46, C48,
INBOX 1357: the class, not the case).
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import act_registry, acts, commands, intent
from tessellate.core.database import Entry, Reminder

NOW = datetime(2026, 10, 29, 10, 0)

VERBS = ["archive", "unarchive", "restore", "split", "merge", "duplicate", "clone", "combine"]
FRAMES = ["{v} the scarecrow joke", "{v} my Atlas kickoff note", "please {v} the lentil soup note", "{v} this note", "Archive".replace("Archive", "{v}") + " the two lentil soup notes"]


@pytest.mark.parametrize("verb", VERBS)
@pytest.mark.parametrize("frame", FRAMES)
def test_an_app_verb_is_an_act_not_a_lookup(verb, frame):
    said = frame.format(v=verb)
    assert act_registry.app_verb(said) == verb, said
    assert intent.classify(said) == intent.ACT, said
    assert "done in the app" in act_registry.app_verb_line(verb)


@pytest.mark.parametrize(
    "said",
    ["how do I archive a note?", "what does merge do", "is the archive empty", "where is the restore button", "I archived the old joke", "tell me about the split"],
)
def test_a_question_about_an_app_verb_is_not_an_act(said):
    assert act_registry.app_verb(said) is None, said


def _stream(ai_client, question, notes_only):
    events = []
    with ai_client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, "notes_only": notes_only}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


@pytest.mark.parametrize("notes_only", [True, False])
@pytest.mark.parametrize("model", [False, True])
@pytest.mark.parametrize("said", ["archive the scarecrow joke", "split the Atlas kickoff note", "merge the two lentil soup notes", "restore the scarecrow joke"])
def test_ask_and_chat_say_where_an_app_verb_is_done(ai_client, fake_ollama, notes_only, model, said):
    fake_ollama.running = model
    if model and not notes_only:
        pytest.skip("with a model up Chat's agent answers; the typed path is the no-model one")
    answer = "".join(e.get("delta", "") for e in _stream(ai_client, said, notes_only) if e["type"] == "answer")
    assert "done in the app" in answer, answer


@pytest.mark.parametrize(
    "said",
    ["move the lentil soup v2 note to the bin", "put the lentil soup v2 note in the trash", "send the lentil soup v2 note to the rubbish", "throw the lentil soup v2 note into the bin"],
)
def test_move_to_the_bin_is_a_delete(said):
    found = commands.read_typed(said, NOW)
    assert found and found["intent"] == "delete" and found["about"] == "lentil soup v2", found


@pytest.mark.parametrize("said", ["remember to buy a capo", "Remember to buy a capo", "remember to buy a capo tomorrow at 9am"])
def test_remember_to_is_a_reminder(said):
    found = commands.read_typed(said, NOW)
    assert found and found["intent"] == "reminder" and found["text"].lower().startswith("buy a capo"), found


@pytest.mark.parametrize("said", ["note that I need new running shoes", "Note that I need new running shoes"])
def test_note_that_makes_a_note(said):
    found = commands.read_typed(said, NOW)
    assert found == {"intent": "new_note", "content": "I need new running shoes"}, found


@pytest.mark.parametrize("said", ["show my reminders", "list my reminders", "show me my reminders", "what reminders do I have"])
def test_reminders_are_listed_not_asked_about(said):
    from tessellate.ai import reading

    got = reading.read(said, now=NOW)
    assert got.tool == "list_reminders" or got.slots.get("surface") == "reminders", (said, got.intent, got.tool)


@pytest.mark.parametrize("said", ["new note: buy milk", "new note buy milk called", "make a note: buy milk"])
def test_the_same_note_twice_asks_first(session, said):
    session.add(Entry(content="Buy milk"))
    session.commit()
    parsed = acts.parse(said if "called" not in said else "new note: buy milk", NOW)
    planned = acts.preview(session, parsed)
    assert "already have" in planned["line"] and "Add another?" in planned["line"]
    assert not planned.get("run")


def test_a_new_note_is_made_at_once(session):
    planned = acts.preview(session, acts.parse("new note: buy bread", NOW))
    assert planned.get("run") is True


@pytest.mark.parametrize("said", ["remind me in 2 hours to stretch", "remind me in 2 hours to Stretch", "remind me tomorrow at 9am to stretch"])
def test_the_same_reminder_twice_asks_first(session, said):
    first = acts.preview(session, acts.parse("remind me in 2 hours to stretch", NOW))
    assert first.get("run") is True

    session.add(Reminder(text="Stretch", due_at=NOW))
    session.commit()
    again = acts.preview(session, acts.parse(said, NOW))
    assert "already have a reminder" in again["line"] and not again.get("run")
