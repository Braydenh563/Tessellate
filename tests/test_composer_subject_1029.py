"""Subject extraction is one rule for the class (audit 1029 C15, C16, C17,
C18, C37; INBOX 1357: a fix holds for the class, not the one example).

The command words an app knows ("read", "draft", "move") are taken off before
the subject is chosen; a capitalised name matches whole words only; a question
about a person is answered in one people shape; "define X" gets a definition
and not a digest; the "not found" footer names content words only. Every case
runs over several subjects and phrasings, in Ask (`notes_only`) and in Chat,
with no model.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import composer, composer_digest
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime


@pytest.fixture
def notebook(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(notes):
        for text, when in notes:
            entry = manager.create_entry(session, text, "Personal")
            entry.created_at = entry.updated_at = when
        session.commit()

        def go(question: str, chat: bool = False) -> str:
            kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
            return _ask(client, question, **kw)["text"]

        return go

    return build


MODES = pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])


# --- command words come off the subject (C15) -------------------------------------

COMMANDS = ["read", "draft", "move", "merge", "split", "compare", "explain", "define", "open", "show", "summarise", "archive"]
OBJECTS = ["lentil soup", "Atlas ideas", "budget", "Lisbon trip"]
FRAMES = ["{v} the {s} note", "please {v} my {s} notes", "{v} me the {s} note", "{v} {s}"]


@pytest.mark.parametrize("verb", COMMANDS)
@pytest.mark.parametrize("obj", OBJECTS)
@pytest.mark.parametrize("frame", FRAMES)
def test_a_leading_command_word_is_not_in_the_subject(verb, obj, frame):
    said = frame.format(v=verb, s=obj)
    stems = composer_digest._subject(said)
    assert composer._stem(verb) not in stems, (said, stems)
    for word in obj.lower().split():
        assert composer._stem(word) in stems, (said, stems)


@pytest.mark.parametrize("said", ["draft a message to Sara", "write an email to Sara", "compose a reply to Sara"])
def test_a_drafting_request_keeps_the_person_only(said):
    assert composer_digest._subject(said) == ["sara"], said


@pytest.mark.parametrize("said", ["merge the two lentil soup notes", "move the budget to the bin", "read me the lentil soup note"])
def test_filler_words_of_a_command_are_not_the_subject(said):
    assert not {"two", "bin", "merg", "merge", "move", "read", "me"} & set(composer_digest._subject(said)), said


@pytest.mark.parametrize("said", ["tell me about books I am reading", "notes about the reading list"])
def test_a_content_word_that_is_also_a_verb_stays_when_it_does_not_open_the_command(said):
    stems = composer_digest._subject(said)
    assert any(st in stems for st in ("read", "plan")), (said, stems)


def test_a_name_with_an_s_keeps_it():
    assert composer_digest._subject("tell me about Project Atlas") == ["project", "atlas"]


SUBJECTS = ["sourdough", "kayaking", "espresso", "violin"]


@MODES
@pytest.mark.parametrize("subject", SUBJECTS)
@pytest.mark.parametrize("frame", ["read the {s} note", "read me the {s} note", "tell me about {s}"])
def test_an_answer_never_prints_the_command_as_the_topic(notebook, subject, frame, chat):
    cap = subject.capitalize()
    go = notebook([(f"# {cap}\n\nThe plan for {subject} this season.", D(2026, 6, 1, 9)), (f"# {cap} diary\n\nWent back to {subject} today.", D(2026, 9, 1, 9))])
    said = go(frame.format(s=subject), chat).lower()
    assert not re.search(r"\babout (read|tell|read me)\b", said), said


# --- a name matches whole words only (C16) ----------------------------------------

NAMES = [("Tom", "tomatoes"), ("Sam", "samosas"), ("Ann", "annual"), ("Kim", "kimchi"), ("Max", "maximum")]


def _people_notebook(name: str, decoy: str):
    return [
        (f"# Kickoff meeting\n\nAttendees: Sara, {name}, Priya", D(2026, 10, 13, 9)),
        (f"# Test note from sweep\n\nTest note from sweep about gardening and {decoy}.", D(2026, 10, 20, 9)),
        (f"# Errands\n\nBuy {decoy} and call the dentist {decoy} at 10am.", D(2026, 10, 21, 9)),
    ]


@MODES
@pytest.mark.parametrize(("name", "decoy"), NAMES)
@pytest.mark.parametrize("frame", ["summarise my notes on {n}", "show me notes about {n}", "what do I know about {n}", "tell me about {n}"])
def test_a_name_never_matches_inside_a_longer_word(notebook, name, decoy, frame, chat):
    go = notebook(_people_notebook(name, decoy))
    said = go(frame.format(n=name), chat)
    assert decoy not in said.lower(), said
    assert "Errands" not in said and "Test note from sweep" not in said, said


# --- one people shape (C17) -------------------------------------------------------

COUNT_OPENING = re.compile(r"^(one|two|three|four|five|six|\d+)\b[,:]", re.I)


@MODES
@pytest.mark.parametrize(("name", "decoy"), NAMES)
@pytest.mark.parametrize("frame", ["what do I know about {n}", "tell me about {n}", "who is {n}"])
def test_a_person_is_answered_in_one_shape(notebook, name, decoy, frame, chat):
    go = notebook(_people_notebook(name, decoy))
    said = go(frame.format(n=name), chat)
    assert not COUNT_OPENING.match(said.strip()), said
    assert "of its own" not in said and "Remind you to try" not in said, said
    #: The closing offer is varied by phrasing; the answer itself is one shape.
    assert said.split("\n\n")[0] == go(f"who is {name}", chat).split("\n\n")[0], said


# --- define X is answered as a definition (C18) -----------------------------------

DEFINED = [
    ("sourdough starter", "A sourdough starter is a live culture of flour and water."),
    ("kombucha", "Kombucha is a fermented tea."),
    ("espresso", "Espresso is a strong coffee pulled under pressure."),
]


@MODES
@pytest.mark.parametrize(("term", "line"), DEFINED)
@pytest.mark.parametrize("frame", ["define {t}", "definition of {t}", "what does {t} mean"])
def test_define_gets_the_definition_not_a_digest(notebook, term, line, frame, chat):
    go = notebook([
        (f"# Bread log\n\nFed the {term} twice today.", D(2026, 8, 2, 9)),
        (f"# Basics\n\n{line}", D(2026, 8, 14, 9)),
        (f"# Shopping\n\nBuy flour, and look for {term} jars.", D(2026, 8, 20, 9)),
    ])
    said = go(frame.format(t=term), chat)
    assert "You have" not in said and "last wrote" not in said, said
    assert line.split(" is ", 1)[1].rstrip(".").lower() in said.lower(), said


# --- the footer lists content words only (C37) ------------------------------------

INSTRUCTION = ["main", "two", "sentences", "tags", "improve", "related", "points", "recur", "similar", "category", "older", "favourite", "everything"]


@pytest.mark.parametrize("word", INSTRUCTION)
def test_an_instruction_word_is_never_reported_missing(notebook, word):
    go = notebook([
        ("# Sourdough\n\nThe starter lives on the counter; feed it every day.", D(2026, 8, 2, 9)),
        ("# Violin\n\nScales before breakfast.", D(2026, 8, 3, 9)),
    ])
    for frame in ("tell me about sourdough {w}", "what do my notes say about the starter and {w}", "{w} sourdough starter"):
        said = go(frame.format(w=word))
        assert f"“{word}”" not in said and f'"{word}"' not in said, said


def test_a_content_word_no_note_holds_is_still_reported_missing(notebook):
    go = notebook([("# Sourdough\n\nThe starter lives on the counter; feed it every day.", D(2026, 8, 2, 9))])
    said = go("what do my notes say about the starter and the hotel")
    assert "hotel" in said.lower(), said
