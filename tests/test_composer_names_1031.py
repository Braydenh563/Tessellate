"""How a note is named in an answer (composer-1031, the brief's item 2): "the
Booked flights to Lisbon", "the Cloud computing" are wrong.

Two classes, each by several phrasings and note shapes:

1. No article before a title or a title-cased opening: a note's own name is
   said as it is ("Cloud computing", "Speed reading tips"); a lower-case
   title is "your trains note"; a title with its own article keeps it.
2. A title-less line that tells what the person did is named by what it is
   about, a clean noun phrase ("your note on flights to Lisbon"), never the
   line worn as a title ("the Booked flights to Lisbon", "the had ...").
"""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer_frame


def _name(content: str) -> str:
    return composer_frame.short_name({"id": 1, "content": content})


@pytest.mark.parametrize(("content", "name"), [
    ("# Cloud computing\n\nNotes on cloud computing: IaaS, PaaS and SaaS.", "Cloud computing"),
    ("# Speed reading tips\n\nSkim the headings first.", "Speed reading tips"),
    ("**Reading list**\n\nMyers chapters 1 to 3.", "Reading list"),
    ("Essay plan:\n\nIntro, two case studies.", "Essay plan"),
    ("Atlas retro meeting", "Atlas retro meeting"),
    ("Advanced calculus", "Advanced calculus"),
])
def test_a_title_is_said_without_an_article(content, name):
    assert _name(content) == name


@pytest.mark.parametrize(("content", "name"), [
    ("# The Complete Social Skills Guide\n\nChapter one.", "The Complete Social Skills Guide"),
    ("# A year of running\n\nJanuary: 40 km.", "A year of running"),
])
def test_a_title_with_its_own_article_keeps_it(content, name):
    assert _name(content) == name


@pytest.mark.parametrize(("content", "name"), [
    ("# trains\n\nThe 8:10 is always late.", "your trains note"),
    ("# shopping\n\nmilk, eggs", "your shopping note"),
])
def test_a_lower_case_title_is_the_persons_note(content, name):
    assert _name(content) == name


@pytest.mark.parametrize(("content", "name"), [
    ("Booked flights to Lisbon", "your note on flights to Lisbon"),
    ("Cooked dinner for Sam", "your note on dinner for Sam"),
    ("Visited grandma in Leeds", "your note on grandma in Leeds"),
    ("Booked dentist appointment for Tuesday", "your note on dentist appointment for Tuesday"),
    ("Finished essay draft", "your note on essay draft"),
    ("Watched Dune with Priya", "your note on Dune with Priya"),
])
def test_a_line_of_what_you_did_is_named_by_what_it_is_about(content, name):
    assert _name(content) == name


@pytest.mark.parametrize("content", [
    "Booked flights to Lisbon", "had design class today for prototyping", "Cooked dinner for Sam",
    "# Cloud computing\n\nIaaS.", "Speed reading tips", "Grilled cheese recipe", "Went to the gym after work",
])
def test_never_an_article_before_a_capital_or_a_verb(content):
    named = _name(content)
    assert not re.match(r"the (?:[A-Z]|had\b|went\b|booked\b)", named), named
