"""Zero, one and many in a composed count (composer9 Remaining, "0 distinct
tags"): the class is any stats answer that states a count.

Zero is "no", never a digit that then asks for a plural noun ("You are using 0
distinct tags"); one takes a singular verb ("1 note out of 3 has no tags", not
"have"); a sentence that cannot be said of nothing says what is true instead
("Every note has a tag"). Each question is asked of a notebook of none, one and
three notes."""

from __future__ import annotations

import json
import re

import pytest

from tessellate.ai import notebook_stats, realise
from tessellate.core import deps
from tessellate.core.database import Entry

QUESTIONS = [
    "how many tags do I have",
    "how many distinct tags",
    "what are my most common tags",
    "how many categories do I have",
    "how many notes do I have",
    "how many documents do I have",
    "how many notes have no tags",
    "how many untagged notes",
    "how many notes are not linked",
    "how many orphan notes",
    "give me an overview of my notebook",
    "what did I write most about",
    "how many words have I written",
    "how many notes did I write this week",
    "how many notes did I write today",
    "stats",
    "summary of my notebook",
]

#: A digit zero before a counted noun, a one before a plural noun, and a
#: singular count with a plural verb ("1 note out of 3 have").
ZERO_NOUN = re.compile(r"(?<![\d.,(#/])\b0 (?!out\b)[a-z]")
ONE_PLURAL = re.compile(r"(?<![\d.,])\b1 (?:distinct )?(?:notes|tags|categories|documents|words|links)\b")
ONE_PLURAL_VERB = re.compile(r"(?<![\d.,])\b1 \w+ out of \d+ (?:are|have)\b")


def _fill(session, notes: int) -> None:
    for entry in session.query(Entry).all():
        session.delete(entry)
    for i in range(notes):
        session.add(Entry(content=f"note {i} about work", tags=json.dumps([] if i == 0 else ["work"])))
    session.commit()


@pytest.mark.parametrize("notes", [0, 1, 3])
@pytest.mark.parametrize("question", QUESTIONS)
def test_a_count_is_said_right_for_none_one_and_many(client, question, notes):
    with deps.get_db().session() as session:
        _fill(session, notes)
        result = notebook_stats.answer(question, session)
    if result is None:
        return
    text = result.text
    assert not ZERO_NOUN.search(text), text
    assert not ONE_PLURAL.search(text), text
    assert not ONE_PLURAL_VERB.search(text), text


@pytest.mark.parametrize("noun", ["note", "tag", "category", "document", "day", "reminder"])
def test_the_shared_counter_says_none_one_and_many(noun):
    none, one, many = (realise.count_noun(n, noun) for n in (0, 1, 3))
    assert none.startswith("no ") and one.startswith("one ") and many.startswith("three ")
    assert one.endswith(noun) and none != f"no {noun}" and many != f"three {noun}"


def test_no_tags_at_all_is_said_as_none_in_use(client):
    with deps.get_db().session() as session:
        _fill(session, 0)
        text = notebook_stats.answer("how many tags do I have", session).text
    assert text == "You are not using any tags yet."


def test_one_note_without_tags_has_a_singular_verb(client):
    with deps.get_db().session() as session:
        _fill(session, 1)
        text = notebook_stats.answer("how many notes have no tags", session).text
    assert text.startswith("1 note out of 1 has no tags"), text


def test_every_note_tagged_is_not_zero_notes_with_no_tags(client):
    with deps.get_db().session() as session:
        _fill(session, 0)
        session.add(Entry(content="tagged", tags=json.dumps(["work"])))
        session.commit()
        text = notebook_stats.answer("how many notes have no tags", session).text
    assert text.startswith("Every note has a tag"), text
