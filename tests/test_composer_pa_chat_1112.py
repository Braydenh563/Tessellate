"""Composer batch A of PR 216 (ledger 1112), the chat rows (F4). No model; clocks fixed by the seeds."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


def say(go, *questions):
    """The last answer of a chat that asked `questions` one after another, history carried."""
    history: list[dict] = []
    text = ""
    for question in questions:
        text, _events = go(question, history=history or None)
        history.append({"question": question, "answer": text})
    return text


# --- F4: social and meta turns read, never searched as a note ------------------------


@pytest.mark.parametrize("typed", ["you're not very helpful", "that's not helpful", "you are not helpful at all", "this is unhelpful", "that was no help", "you're not that useful"])
def test_f4_a_complaint_about_the_help_is_answered_not_searched(go, typed):
    said, _ = go(typed)
    assert "Fair" in said or "Sorry" in said or "Point taken" in said, said
    assert "mention" not in said.lower() and "coriander" not in said.lower(), said


@pytest.mark.parametrize("typed", ["what did I just add", "what did I just write", "what have I last saved", "what did I just save"])
def test_f4_what_did_i_just_add_is_the_newest_note(go, typed):
    said, _ = go(typed)
    assert "Weekly review" in said, said


@pytest.mark.parametrize(
    "typed,expect",
    [("say that again", "Once more"), ("really?", "only say what your notes"), ("are you sure", "word for word"), ("yep", "")],
)
def test_f4_the_bare_reactions_lean_on_the_answer_before(go, typed, expect):
    said = say(go, "what's on my todo", typed)
    assert expect in said, said
    assert "mention" not in said.lower()
