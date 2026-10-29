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


# --- 2: a properties block reads the same with any line ending ----------------------------

BLOCKS = [
    "---\ntags: [meeting, atlas]\nstatus: open\n---\n# Atlas sync\n\nBeta scope is frozen.",
    "---\ntype: Book\nauthor: Powers\n---\nThe Overstory, a slow start.",
    "---\naliases:\n  - sync\n  - weekly\n---\n\n# Weekly\n\n- [ ] draft the spec",
]


@pytest.mark.parametrize("text", BLOCKS, ids=["tags", "book", "list"])
def test_a_crlf_block_ends_where_its_lf_twin_does(text):
    from tessellate.entry import properties

    crlf = text.replace("\n", "\r\n")
    lf_end, crlf_end = properties.block_end(text), properties.block_end(crlf)
    assert lf_end
    assert crlf_end
    assert crlf[crlf_end:] == text[lf_end:].replace("\n", "\r\n")


@pytest.mark.parametrize("text", BLOCKS, ids=["tags", "book", "list"])
def test_a_crlf_block_reads_the_same_properties(text):
    from tessellate.entry import properties

    assert properties.split(text.replace("\n", "\r\n"))[0] == properties.split(text)[0]


@pytest.mark.parametrize("text", BLOCKS, ids=["tags", "book", "list"])
def test_a_crlf_note_is_never_named_by_its_fence(text):
    from tessellate.ai import composer

    view = composer.read_note({"id": 1, "content": text.replace("\n", "\r\n"), "created_at": NOW, "updated_at": NOW}, 0)
    assert view is not None
    assert view.title.strip("-") != "", view.title


# --- 3: a checklist asked for by name is shown, not quoted as facts -----------------------

#: (the note, the questions that name it). Each note is only a checklist.
CHECKLIST_NOTES = [
    ("# Checklist\n\n- [ ] tent\n- [ ] stove\n- [x] torch", ["what is the checklist note", "what is the checklist", "what is in my checklist", "tell me about checklist"]),
    ("# Gear\n\n- [ ] tent\n- [ ] stove\n- [x] torch", ["what is the gear note", "what is in my gear list", "tell me about gear", "what is my gear"]),
    ("# Chores\n\n- [ ] sweep\n- [ ] mop\n- [ ] bins", ["what is the chores note", "what is on my chores list", "tell me about chores"]),
]


@MODES
@pytest.mark.parametrize(("text", "questions"), CHECKLIST_NOTES, ids=["checklist", "gear", "chores"])
def test_a_checklist_asked_for_by_name_is_shown_as_the_checklist(book, text, questions, chat):  # noqa: F811
    ask = book([(text, D(2026, 10, 23, 9))])
    found = []
    for q in questions:
        said = ask(q, chat)
        if "- [ ] " not in said or "**Also:**" in said:
            found.append(f"{q}\n{said}")
    assert not found, "\n\n".join(found)


# --- 4: "summarise my week" is the week's recap --------------------------------------------

RECAPS = [
    ("what did I do this week", ["summarise my week", "summarize my week", "summarise this week", "recap my week", "sum up the week",
                                  "give me a recap of my week", "please summarise my week", "can you summarise this week"]),
    ("what did I do last week", ["summarise last week", "recap last week", "sum up my last week"]),
    ("what did I do this month", ["summarise my month", "recap this month", "summarise the month"]),
    ("what did I do yesterday", ["summarise yesterday", "recap yesterday"]),
]


@MODES
@pytest.mark.parametrize(("canonical", "asks"), RECAPS, ids=["week", "last-week", "month", "yesterday"])
def test_a_summary_of_a_period_is_that_periods_recap(book, canonical, asks, chat):  # noqa: F811
    ask = book([("Thinking about the week ahead and what to plan", D(2026, 10, 28, 9))])
    want = ask(canonical, chat)
    assert " you " in want.split(":")[0], want
    found = [f"{q}\n{said}" for q in asks if (said := ask(q, chat)) != want]
    assert not found, "\n\n".join(found)


@pytest.mark.parametrize("question", ["summarise my gym notes", "summarise the week ahead plan", "summarise my week at the cafe"])
def test_a_summary_of_a_subject_is_not_a_recap(question):
    from tessellate.ai import activity

    assert activity.read(question, NOW.date()) is None


# --- 5: the lead note is the one the subject names, not the one a verb matches ------------

LEADS = [
    ("what should I buy for my sister", "Sister", "Guitar"),
    ("what should I get my sister", "Sister", "Guitar"),
    ("what can I buy for my sister", "Sister", "Guitar"),
    ("what do I need to buy for the guitar", "Guitar", "Sister"),
]


@MODES
@pytest.mark.parametrize(("question", "lead", "never"), LEADS)
def test_the_lead_note_is_the_one_the_subject_names(book, question, lead, never, chat):  # noqa: F811
    ask = book([
        ("# Guitar\n\n- [ ] buy a capo\n- [ ] restring the guitar", D(2026, 10, 15, 9)),
        ("# Sister\n\nMy sister's birthday is on 3 December. She likes the sourdough I make.", D(2026, 10, 16, 9)),
    ])
    said = ask(question, chat)
    assert lead in said and f"{never} note" not in said and f"**{never}**" not in said, said
