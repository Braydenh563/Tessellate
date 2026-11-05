"""Audit 1028 E24: a generative ask (an essay, a timetable, a poem, an email,
"explain it simply") is answered with a line that says a model writes it, never
with note quotes. One list of generative verbs and things; many phrasings."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import composer, intent, utilities

NOW = datetime(2026, 11, 2, 9, 0)

GENERATIVE = [
    "write me an essay intro on WW1",
    "write an essay about the Krebs cycle",
    "Can you write me a poem about sourdough?",
    "please draft an email to the landlord",
    "draft a message to Sara",
    "give me a study plan for next week",
    "give me a revision timetable",
    "make a timetable for revision",
    "make me a revision schedule",
    "create a meal plan for the week",
    "come up with a story about a dragon",
    "compose a song about exams",
    "generate a cover letter",
    "help me write a speech for the wedding",
    "I need a paragraph about photosynthesis",
    "explain the Krebs cycle simply",
    "explain recursion like I'm five",
    "explain entropy in simple terms",
    "write a short story",
    "put together a workout plan",
]
NOT_GENERATIVE = [
    "write down milk",
    "create a note called Shopping with milk, eggs and bread",
    "make a note about my essay",
    "write a note about the dentist",
    "make a reminder for Friday",
    "create a checklist for the trip",
    "make a shopping list",
    "give me my schedule",
    "what did I write about my essay",
    "plan my week",
    "explain",
    "what is on my timetable",
    "remind me to write the essay on Friday",
    "give me an outline of the databases lecture",
    "outline lecture 5",
    "give me a summary of my notes on WW1",
]


@pytest.mark.parametrize("ask", GENERATIVE)
def test_a_generative_ask_says_it_needs_a_model(ask):
    assert utilities.kind_of(ask) == "generate", ask
    assert intent._classify(ask) == intent.UTILITY
    said = composer.compose(ask, [], today=NOW.date(), now=NOW)
    assert said and said["shape"] == "utility"
    assert "needs a model" in said["text"] and "Settings" in said["text"]
    assert "\u2014" not in said["text"] and "!" not in said["text"]


@pytest.mark.parametrize("ask", GENERATIVE[:4])
def test_it_is_not_answered_from_notes_even_when_a_note_matches(ask):
    notes = [{"id": 1, "content": "Sourdough: feed the starter, then bake at 230.", "created_at": "2026-10-01"}]
    said = composer.compose(ask, notes, today=NOW.date(), now=NOW)
    assert "needs a model" in said["text"] and "starter" not in said["text"]


@pytest.mark.parametrize("ask", NOT_GENERATIVE)
def test_a_note_command_or_a_notes_question_is_not_generative(ask):
    assert utilities.kind_of(ask) != "generate", ask


@pytest.mark.parametrize("ask", ["write me an essay intro on WW1", "make a timetable for revision", "give me a study plan for next week"])
def test_through_the_route_with_no_model_the_reply_is_the_needs_a_model_line(client, session, ask):
    import json

    from tessellate.entry import manager

    manager.create_entry(session, "# WW1 revision\n\nCauses of the war, the alliances, the timetable of battles.")
    session.commit()
    with client.stream("POST", "/chat/stream", json={"question": ask, "use_tools": False}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    said = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    assert "needs a model" in said and "alliances" not in said, said


def test_with_a_model_running_a_generative_ask_goes_to_chat(monkeypatch):
    from tessellate.api import routes_chat

    class _Running:
        def is_running(self):
            return True

    monkeypatch.setattr(routes_chat.deps, "get_ollama", lambda: _Running())
    assert routes_chat._worked_out("write me an essay intro on WW1") == (intent.SMALLTALK, None)
