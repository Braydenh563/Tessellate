"""INBOX 1561 (d): half of a sentence ("After making an initial connection.") that a
list finishes is never quoted as a whole sentence."""

from __future__ import annotations

import json

import pytest

from tessellate.entry import manager

FRAGMENTS = [
    "After making an initial connection.", "Before leaving the house.", "When arriving at the airport.",
    "While waiting for the bus.", "Upon reaching the summit.", "By adding more salt.", "Without asking first.",
]
WHOLE = [
    "After making coffee, I left.", "Before leaving I locked up.", "When arriving at the airport we found the gate shut.",
    "While waiting for the bus, read the timetable.", "After making an initial connection, ask about their week.",
]


@pytest.mark.parametrize("text", FRAGMENTS)
def test_a_clause_with_no_main_clause_is_not_a_sentence(text):
    from tessellate.ai import composer_read

    assert composer_read._dependent_fragment(text), text


@pytest.mark.parametrize("text", WHOLE)
def test_a_whole_sentence_stays(text):
    from tessellate.ai import composer_read

    assert not composer_read._dependent_fragment(text), text


@pytest.mark.parametrize("fragment", FRAGMENTS[:4])
@pytest.mark.parametrize("question", ["what do I have about interesting", "what did I write about conversation starters"])
def test_the_answer_never_quotes_the_fragment_alone(client, session, fragment, question):
    manager.create_entry(session, f"# Conversation starters\n\n{fragment}\n\n- Ask something interesting about their week.\n- Keep it light.\n")
    manager.create_entry(session, "# Interesting bean\n\nAn interesting bean from the market, roasted dark.")
    session.commit()
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    said = ""
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip() and json.loads(line)["type"] == "answer":
                said += json.loads(line)["delta"]
    assert fragment.rstrip(".").lower() not in said.lower(), said
