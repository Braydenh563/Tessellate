"""The composer's found-not-fixed leftovers (audit 1029, composer-1029b.md).

Each test runs over the class, in Ask (`notes_only`) and in Chat, with no model.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.api import routes_chat
from tessellate.entry import manager
from tests.test_composer_grammar_1029b import book  # noqa: F401  (the fixture)

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime

MODES = pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])

#: Words that join a sentence and name nothing: never what a note is about.
FUNCTION_WORDS = ("about", "above", "after", "again", "against", "also", "because", "before", "between", "during",
                  "other", "over", "some", "such", "through", "under", "until", "while", "which", "where")


# --- 1: a stop word is never a topic ------------------------------------------------------


@pytest.mark.parametrize("word", FUNCTION_WORDS)
def test_a_function_word_is_never_the_word_a_note_is_about(session, word):
    manager.create_entry(session, f"{word.capitalize()} cats and dogs, and the garden")
    session.commit()
    assert routes_chat._newest_word(session) not in FUNCTION_WORDS


@pytest.mark.parametrize("title", ["Note 1 about cats", "Note 2 about cats", "Notes about cats"])
def test_a_note_titled_note_n_about_x_is_about_x(session, title):
    manager.create_entry(session, title)
    session.commit()
    assert routes_chat._newest_word(session) == "cats"


@pytest.mark.parametrize("word", FUNCTION_WORDS)
def test_a_function_word_is_never_the_topic_of_the_last_question(word):
    history = [{"question": f"what did I write {word} cats", "answer": f"Three notes {word} cats, and more."}]
    assert routes_chat._chat_topic(history) == "cats"


@MODES
@pytest.mark.parametrize("greeting", ["hi", "hello", "hey there", "good morning"])
def test_a_greeting_never_offers_about_as_a_topic(book, greeting, chat):  # noqa: F811
    ask = book([("Note 3 about cats", D(2026, 10, 28, 9))])
    said = [ask(f"{greeting}{' ' * n}", chat) for n in range(8)]
    bad = [s for s in said if re.search(r"(?:on|about|of|to) about\b|“what did I write about about”", s)]
    assert not bad, bad
