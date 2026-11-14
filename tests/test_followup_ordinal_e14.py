"""Audit 1028 E14: a next question names the answer's notes by place ("pin the
second one", "the last one", "which of those is first", "compare those").

The class: a reference to the previous answer's cited notes by position or as a
group, with or without a verb, in an act or a question. Each is resolved against
the cited notes (`objects`) the same way on every path, model up or down
(decision 75); a place the answer does not have, or a sentence with its own
subject, is never guessed at.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import reading

NOW = datetime(2026, 10, 29, 10, 0)
TURNS = [{"text": "what do I know about trips", "objects": ["Lisbon trip", "Tokyo trip", "Porto weekend"]}]


@pytest.mark.parametrize(
    ("said", "title"),
    [
        ("pin the second one", "Tokyo trip"),
        ("pin the 2nd one", "Tokyo trip"),
        ("pin the second note", "Tokyo trip"),
        ("pin the second", "Tokyo trip"),
        ("open the first note", "Lisbon trip"),
        ("open the first one", "Lisbon trip"),
        ("please open the 1st", "Lisbon trip"),
        ("delete the last one", "Porto weekend"),
        ("pin the last", "Porto weekend"),
        ("tag the third one with holiday", "Porto weekend"),
        ("rename the first one to Portugal", "Lisbon trip"),
        ("pin number 2", "Tokyo trip"),
        ("summarise the third one", "Porto weekend"),
    ],
)
def test_a_place_in_the_answer_names_that_note(said, title):
    got = reading.cited_follow(said, TURNS, NOW)
    assert got is not None and f"the {title} note" in got, (said, got)


@pytest.mark.parametrize(
    ("said", "title"),
    [
        ("the second one", "Tokyo trip"),
        ("the first one", "Lisbon trip"),
        ("the last one", "Porto weekend"),
        ("what about the second", "Tokyo trip"),
        ("how about the third one", "Porto weekend"),
        ("and the first?", "Lisbon trip"),
    ],
)
def test_a_bare_place_asks_about_that_note(said, title):
    got = reading.cited_follow(said, TURNS, NOW)
    assert got is not None and got.startswith("tell me more about") and f"the {title} note" in got, (said, got)


@pytest.mark.parametrize(
    ("said", "adjective"),
    [
        ("which of those is first", "oldest"),
        ("which one is newest", "newest"),
        ("which of these is the oldest", "oldest"),
        ("which of those is the latest", "newest"),
        ("which is cheaper of those", "cheaper"),
        ("which of them is sooner", "sooner"),
    ],
)
def test_which_of_those_is_a_comparison_of_the_cited_notes(said, adjective):
    got = reading.cited_follow(said, TURNS, NOW)
    assert got == f"which is {adjective}, Lisbon trip, Tokyo trip or Porto weekend", (said, got)


@pytest.mark.parametrize("said", ["compare those", "compare them", "compare these", "compare both", "compare the two"])
def test_a_group_is_every_cited_note(said):
    got = reading.cited_follow(said, TURNS, NOW)
    assert got == "compare Lisbon trip, Tokyo trip and Porto weekend", (said, got)


@pytest.mark.parametrize(
    "said",
    [
        "pin the fifth one",
        "open the first aid note",
        "what about the second world war",
        "the second world war notes",
        "pin the second hand bookshop note",
        "which is the newest note about running",
        "compare those two recipes in the cookbook",
    ],
)
def test_no_place_the_answer_lacks_and_no_sentence_with_its_own_subject_is_guessed(said):
    assert reading.cited_follow(said, TURNS, NOW) is None, said


def test_one_cited_note_has_no_second_and_no_group():
    one = [{"text": "what is my squat", "objects": ["Gym log"]}]
    assert reading.cited_follow("pin the second one", one, NOW) is None
    assert reading.cited_follow("compare those", one, NOW) is None
    assert reading.cited_follow("which of those is first", one, NOW) is None
    got = reading.cited_follow("pin the first one", one, NOW)
    assert got is not None and "the Gym log note" in got


def test_with_nothing_cited_nothing_is_guessed():
    assert reading.cited_follow("pin the second one", [{"text": "hello", "objects": []}], NOW) is None


def _stream(ai_client, question, history):
    events = []
    with ai_client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, "history": history}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


@pytest.mark.parametrize("said", ["pin the second one", "pin the 2nd one", "pin the second note"])
def test_chat_with_no_model_pins_the_second_cited_note(ai_client, fake_ollama, session, said):
    from tessellate.ai import tools

    fake_ollama.running = False
    tools.execute_tool(session, "create_note", {"content": "Lisbon trip: flights on 14 March"})
    tools.execute_tool(session, "create_note", {"content": "Tokyo trip: flights on 2 May"})
    session.commit()
    history = [{"question": "what do I know about trips", "answer": "Two notes.", "objects": ["Lisbon trip", "Tokyo trip"]}]
    card = next((e for e in _stream(ai_client, said, history) if e["type"] == "act"), None)
    assert card is not None, said
    assert card["steps"][0]["arguments"]["note_id"] == 2


@pytest.mark.parametrize("said", ["compare those", "which of those is oldest"])
def test_chat_with_no_model_reads_the_group_not_the_word(ai_client, fake_ollama, session, said):
    from tessellate.ai import tools

    fake_ollama.running = False
    tools.execute_tool(session, "create_note", {"content": "Lisbon trip: flights on 14 March"})
    tools.execute_tool(session, "create_note", {"content": "Tokyo trip: flights on 2 May"})
    session.commit()
    history = [{"question": "what do I know about trips", "answer": "Two notes.", "objects": ["Lisbon trip", "Tokyo trip"]}]
    text = "".join(e.get("delta", "") for e in _stream(ai_client, said, history) if e["type"] == "answer")
    assert "Lisbon" in text and "Tokyo" in text, text
    assert "own tools" not in text and "No mention" not in text and "found no mention" not in text, text
