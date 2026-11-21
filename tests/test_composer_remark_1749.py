"""Social turns answered like a person (INBOX 1749, the owner: "heyy" got a
status report with a note card, "Its been really hot today" got "Not sure what
you mean" with stats chips). Each fixture is a turn the composer got wrong:
a greeting matches the person's register, a remark gets a short human reply
and at most one gentle note link, and a social turn has no "not sure what you
mean", no Sources and no stats chips. The model path is handed the same
facts (CHAT_PLAN decision 75). Clock: Saturday 31 October 2026, 11:30."""

from __future__ import annotations

import json

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import composer_remark
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager

# --- the register of a hello ------------------------------------------------------

CASUAL = ["heyy", "hey", "hi", "yo", "sup", "hiya", "howdy", "morning", "hey there", "evening all"]
FORMAL = ["hello", "good morning", "Good afternoon", "good evening", "greetings"]


@pytest.mark.parametrize("message", CASUAL)
def test_a_casual_hello_is_read_as_casual(message):
    assert composer_remark.register(message) == "casual"


@pytest.mark.parametrize("message", FORMAL)
def test_a_written_hello_is_read_as_formal(message):
    assert composer_remark.register(message) == "formal"


def test_a_casual_hello_mirrors_the_word_and_the_stretch():
    assert composer_remark.casual_hello("heyy", "natural", [], "s").startswith("Heyy.")
    #: A long stretch is shortened, never repeated back (a stretched word is no nickname, INBOX 1459).
    assert composer_remark.casual_hello("heyyyyy", "natural", [], "s").startswith("Heyy.")
    assert composer_remark.casual_hello("yo", "natural", [], "s").startswith("Yo.")


# --- the remarks, by kind -----------------------------------------------------------

REMARKS = [
    # weather
    "Its been really hot today", "it's raining", "its freezing outside", "nice weather today",
    # feelings and the day
    "what a day", "ugh work", "work was rough", "had a great day", "i couldn't sleep last night", "slept badly",
    # food
    "i'm hungry", "i had pizza for dinner", "i'm cooking tonight",
    # going and wishes
    "I'm going to the gym", "going for a run", "off to bed", "happy birthday", "merry christmas",
    # asks of Atlas that are not about the notes
    "whats up", "do you like music", "Hello, I hope you're well",
]

#: Things that are not remarks: a question, a command or a note-bearing ask.
NOT_REMARKS = [
    "what did I write about the heat", "remind me to go to the gym tomorrow", "show my notes about sleep",
    "when is the gym class", "how many notes do I have", "what's the weather note", "make a note that it is hot",
]


@pytest.mark.parametrize("message", REMARKS)
def test_a_remark_gets_a_line(message):
    line = composer_remark.reply(message, [], "seed", "natural")
    assert line is not None and line[0].strip(), message


@pytest.mark.parametrize("message", NOT_REMARKS)
def test_a_question_or_command_is_not_a_remark(message):
    assert composer_remark.reply(message, [], "seed", "natural") is None, message


def test_a_topic_word_never_finds_a_longer_word():
    import re

    pattern = re.compile(composer_remark.topic_pattern("hot"), re.I)
    assert pattern.search("a hot day") and not pattern.search("Hotel Alfama")
    assert re.search(composer_remark.topic_pattern("sleep"), "I slept badly", re.I)
    assert re.search(composer_remark.topic_pattern("run"), "went for a ran", re.I)


# --- the whole turn, no model -------------------------------------------------------

SOCIAL = [
    *CASUAL, "heyy", "how are you", "thanks", "thank you", "cheers", "lol", "bye", "goodnight", "you're great",
    *REMARKS,
]
NO_CHIPS_BAD = ("Show notes per", "Notebook statistics", "What did I write this week?", "What can you do?")


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("message", SOCIAL)
def test_a_social_turn_has_no_not_sure_no_sources_and_no_stats_chips(go, message):
    said, events = go(message)
    kinds = {e.get("type") for e in events}
    assert said.strip(), message
    assert "not sure what you mean" not in said.lower(), said
    assert "grounding" not in kinds and "sources" not in kinds, (message, kinds)
    asked = [a for e in events if e.get("type") == "offer" for a in e["offer"].get("asks", [])]
    assert not [a for a in asked if a.startswith(NO_CHIPS_BAD)], (message, asked)


@pytest.mark.parametrize("message", CASUAL)
def test_a_casual_hello_is_a_line_not_a_status_report(go, message):
    said, events = go(message)
    assert len(said) < 80, said
    assert "#/notes/" not in said and "reminder" not in said.lower() and "days running" not in said, said
    assert not any(e.get("type") in ("card", "note", "sees") for e in events), message


@pytest.mark.parametrize("message", ["good morning", "Good afternoon"])
def test_a_formal_hello_keeps_the_welcome(go, message):
    said, _ = go(message)
    assert "welcome back" in said and "days running" in said, said
    assert not said.startswith("And") and ". And " not in said, said


@pytest.mark.parametrize("message", ["Its been really hot today", "it's raining", "I'm going to the gym", "merry christmas"])
def test_a_remark_links_at_most_one_note(go, message):
    said, _ = go(message)
    assert said.count("](#/notes/") <= 1, said


def test_a_remark_with_no_note_on_it_has_no_link(go):
    said, _ = go("Its been really hot today")
    assert "#/notes/" not in said and "Hotel" not in said, said


def test_a_remark_is_not_read_as_a_notes_question():
    from tessellate.ai import intent

    for message in ("happy friday", "Its been really hot today", "I need a coffee"):
        assert intent.classify(message) == intent.SMALLTALK, message


# --- the model path is handed the same facts ------------------------------------------

NOTES = [
    ("Diary: it was a hot day at the beach, so I stayed in the shade", "Life", "2026-10-20T10:00:00"),
    ("Dentist on Friday at 3pm", "Life", "2026-10-28T10:00:00"),
]


@pytest.fixture
def seeded(session):
    for content, cat, when in NOTES:
        entry = manager.create_entry(session, content, category_name=cat)
        from datetime import datetime

        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
    session.commit()
    return session


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: seed_c.NOW)
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: seed_c.NOW)


def _stream(client, question: str) -> dict:
    out: dict = {}
    with client.stream("POST", "/chat/stream", json={"question": question}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                out.setdefault(event["type"], []).append(event)
    return out


def _sent(fake) -> str:
    rounds = [*fake.chat_calls[-1:], *fake.tool_rounds[-1:]]
    return "\n".join(str(m.get("content") or "") for messages in rounds for m in messages)


def test_a_model_is_told_a_remark_is_not_a_request(ai_client, fake_ollama, seeded):
    _stream(ai_client, "Its been really hot today")
    assert "made a remark, not a request" in _sent(fake_ollama)


def test_a_model_is_handed_the_one_note_that_bears_on_a_remark(ai_client, fake_ollama, seeded):
    _stream(ai_client, "Its been really hot today")
    assert "hot day at the beach" in _sent(fake_ollama) or "Diary" in _sent(fake_ollama)


def test_a_model_hello_is_handed_the_casual_line(ai_client, fake_ollama, seeded):
    _stream(ai_client, "heyy")
    sent = _sent(fake_ollama)
    assert "Heyy" in sent and "days running" not in sent, sent[-500:]


def test_a_model_remark_has_no_stats_chips(ai_client, fake_ollama, seeded):
    out = _stream(ai_client, "Its been really hot today")
    asked = [a for e in out.get("offer", []) for a in e["offer"].get("asks", [])]
    assert not [a for a in asked if a.startswith(NO_CHIPS_BAD)], asked
