"""L-chat-182 (the owner: "not every chat response needs to be related to notes if it is other things about the
application"): a question about a part of the app is answered from the app's own help, in Ask and in Chat, and is
not turned into "that's general knowledge" or a reading of unrelated notes. A world question still is."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture()
def ask(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    return lambda q, notes_only: sd.ask(client, q, notes_only=notes_only)["text"]


@pytest.mark.parametrize("notes_only", [True, False], ids=["ask", "chat"])
@pytest.mark.parametrize(
    ("question", "says"),
    [
        ("what is the graph tab", "Graph tab shows notes"),
        ("what does the graph tab do", "Graph tab shows notes"),
        ("what can the graph tab do", "Graph tab shows notes"),
        ("what does the whiteboard do", "pannable canvas"),
        ("what's the bin for", "goes to the bin"),
        ("how do I turn on dark mode", "Appearance controls theme (light/dark/system)"),
    ],
)
def test_a_question_about_the_app_is_answered_from_its_help(ask, notes_only, question, says):
    text = ask(question, notes_only)
    assert says in text, text
    assert "general knowledge" not in text


@pytest.mark.parametrize("notes_only", [True, False], ids=["ask", "chat"])
def test_a_question_about_the_world_is_still_the_worlds(ask, notes_only):
    assert "general knowledge" in ask("what is the capital of France", notes_only)


def test_a_note_that_names_the_thing_keeps_the_question(ask):
    #: "starter" is a keyword of the Templates help; the notes have a starter, and the name of the topic is not in the question.
    assert "Templates" not in ask("what does a sourdough starter do", True)
