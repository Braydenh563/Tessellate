"""Composer batch A of PR 216 (ledger 1112), the acts rows (O6, D23, F3). No model; clocks fixed by the seeds."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tests._app_js import app_js_text


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


# --- O6, D23, F3: "undo" after an act ----------------------------------------------


@pytest.mark.parametrize("typed", ["undo", "Undo that", "undo it.", "undo the delete", "undo the last change", "undo that please", "undo the delete please", "redo the change"])
def test_o6_the_ways_to_say_undo_run_the_apps_undo(typed):
    import re

    words = re.search(r"const CHAT_UNDO_WORDS = /(.+?)/i;", app_js_text()).group(1)
    assert re.fullmatch(words, typed, re.I), typed


@pytest.mark.parametrize("typed", ["undo the tag on my essay note", "how do I undo", "undo my dentist note", "what does undo do"])
def test_o6_a_sentence_about_something_else_is_still_a_question(typed):
    import re

    words = re.search(r"const CHAT_UNDO_WORDS = /(.+?)/i;", app_js_text()).group(1)
    assert not re.fullmatch(words, typed, re.I), typed


@pytest.mark.parametrize("ask", ["delete the todo note", "pin the todo note", "tag the todo note work", "remind me to call mum tomorrow", "tick off renew passport"])
def test_d23_every_act_wording_names_what_comes_next(go, ask):
    """A card names Confirm and Cancel; an act that ran says what it did and that Undo takes it back."""
    said, _ = go(ask)
    assert ("Confirm" in said and "Cancel" in said) or "Undo" in said, said
    assert "Undo key" not in said and "status bar" not in said, said


def test_f3_typed_undo_that_reaches_the_server_gets_the_keys_not_a_note_search(go):
    """Where the page does not catch it (Ask, the slash path) the server still answers the keys."""
    said = say(go, "delete the todo note", "undo")
    assert "Ctrl+Z" in said or "Undo" in said, said
    assert "mention" not in said.lower()
