"""A follow-up's "it", "that", "the X" and "more" mean the leading note the
previous answer cited (audit 1029 C44, INBOX 1357: the class, not the case).

The turns carry `objects` as the real client builds them
(`chatTurnObjects` in chat-attach.js: the first sentence of each cited
note's label), so the test does not lean on a first-line title of its own.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import reading

NOW = datetime(2026, 10, 29, 10, 0)
TURNS = [{"text": "what do I know about sourdough", "objects": ["Sourdough starter notes", "Bread schedule", "Dentist"]}]
LEAD = "Sourdough starter notes"


@pytest.mark.parametrize(
    "said",
    [
        "open it", "open that", "open that one", "show it", "show me that", "summarise it", "summarize that",
        "rename it to Run log", "pin it", "tag it with baking", "delete that", "explain it", "read it",
        "tell me more about it", "tell me more about that", "remind me about it tomorrow at 9am",
        "compare it with the ice breakers", "and open it", "please summarise it", "can you open it",
        "link it to the gym note", "what is in it", "what does it say", "what's in that",
    ],
)
def test_it_and_that_mean_the_leading_cited_note(said):
    got = reading.follow(said, TURNS, NOW)
    assert got is not None, said
    assert LEAD in got[0], (said, got)
    assert "Bread schedule" not in got[0]


@pytest.mark.parametrize(
    "said",
    ["tell me more about the starter", "open the starter", "summarise the starter", "show me the sourdough starter", "more about the starter"],
)
def test_the_x_naming_a_word_of_a_cited_title_is_that_note(said):
    got = reading.follow(said, TURNS, NOW)
    assert got is not None and LEAD in got[0], (said, got)


def test_the_x_is_the_cited_note_that_holds_the_word():
    got = reading.follow("open the schedule", TURNS, NOW)
    assert got is not None and "Bread schedule" in got[0]


@pytest.mark.parametrize("said", ["tell me more", "more", "go on", "what else", "and what else", "tell me more about that"])
def test_a_bare_more_asks_for_more_of_the_leading_note(said):
    got = reading.follow(said, TURNS, NOW)
    assert got is not None and LEAD in got[0] and got[0].startswith("tell me more about"), (said, got)


@pytest.mark.parametrize(
    "said",
    ["open the dentist note", "tell me more about running", "open the boiler", "what is the weather", "find notes about the starter", "tell me more about the garden"],
)
def test_a_sentence_that_names_its_own_subject_stands_alone(said):
    got = reading.follow(said, TURNS, NOW)
    #: "the dentist note" is a cited title too: it may resolve to that note, never to the leading one.
    assert got is None or LEAD not in got[0], (said, got)


def test_with_no_cited_note_nothing_is_guessed():
    assert reading.follow("open it", [{"text": "hello there", "objects": []}], NOW) is None
    assert reading.follow("tell me more", [], NOW) is None


def test_the_reading_is_the_act_on_the_cited_note():
    got = reading.read("rename it to Run log", now=NOW, context={"turns": TURNS})
    assert got.intent == "rename" and got.slots["follows"] == "pronoun"
    assert "Sourdough starter notes" in got.said


def _stream(ai_client, question, history):
    import json

    events = []
    with ai_client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, "history": history}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def _seeded(session):
    from tessellate.ai import tools

    tools.execute_tool(session, "create_note", {"content": "Sourdough starter notes: feed it at night"})
    tools.execute_tool(session, "create_note", {"content": "Bread schedule: bake on Saturday"})
    session.commit()
    return [{"question": "what do I know about sourdough", "answer": "Two notes.", "objects": ["Sourdough starter notes", "Bread schedule"]}]


@pytest.mark.parametrize("said", ["rename it to Run log", "rename that to Run log", "rename the starter to Run log"])
def test_chat_with_no_model_acts_on_the_leading_cited_note(ai_client, fake_ollama, session, said):
    fake_ollama.running = False
    card = next((e for e in _stream(ai_client, said, _seeded(session)) if e["type"] == "act"), None)
    assert card is not None
    assert card["steps"][0]["arguments"]["note_id"] == 1


@pytest.mark.parametrize("said", ["tell me more about it", "tell me more about the starter", "open that"])
def test_chat_with_a_model_up_is_given_the_same_named_note(ai_client, fake_ollama, session, said):
    """Decision 75: the model is asked about the note the answer cited, not
    about the bare "it" (the same referent as with no model)."""
    fake_ollama.running = True
    _stream(ai_client, said, _seeded(session))
    seen = " ".join(str(m.get("content")) for call in fake_ollama.chat_calls + fake_ollama.tool_rounds for m in call)
    assert "Sourdough starter notes note" in seen
