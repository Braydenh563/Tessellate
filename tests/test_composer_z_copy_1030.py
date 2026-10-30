"""Composer audit 2026-10-30, classes 7 and 8 (Z47, Z48, Z50): an opener never
claims a process that did not happen, a connector never claims a relation the
notes do not have, and a name a note holds is a lookup before it is a persona."""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer_lines, composer_tables
from tests import _seed_1030 as seed_1030

#: Every one of these said "I am doing something" in front of a quote.
PROCESS = re.compile(
    r"\b(?:let me (?:check|see|rummage)|scanning|checking (?:your|what)|looking at (?:the calendar|your notes|other entries|a separate)|"
    r"flipping pages|notebook (?:is )?open|calendar open|gathering from|diving into|rummage)\b",
    re.I,
)
#: And these said the next note is unrelated, whatever it was.
UNRELATED = re.compile(
    r"\b(?:changing gears|changing tack|pivoting|off to the side|somewhere else entirely|"
    r"completely different|totally different|unrelated notes|different track)\b",
    re.I,
)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _strings(item)
    elif hasattr(value, "text"):
        yield value.text


def _tables():
    """The wording the composer picks from: openers, joiners and the added families."""
    for name in ("OPENERS", "ABILITY_OPENERS"):
        yield name, getattr(composer_lines, name)
    yield "_FAMILIES_ADDED", composer_tables._FAMILIES_ADDED  # noqa: SLF001
    yield "_FAMILIES", composer_tables._FAMILIES  # noqa: SLF001


@pytest.mark.parametrize("name,table", list(_tables()))
def test_z47_no_opener_claims_a_process(name, table):
    bad = [s for s in _strings(table) if PROCESS.search(s)]
    assert not bad, (name, bad)


@pytest.mark.parametrize("name,table", list(_tables()))
def test_z48_no_connector_claims_the_notes_are_unrelated(name, table):
    bad = [s for s in _strings(table) if UNRELATED.search(s)]
    assert not bad, (name, bad)


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    return seed_1030.asker(client, monkeypatch, chat=True)


@pytest.mark.parametrize("question", ["atlas", "what is Atlas", "what's atlas"])
def test_z50_a_name_a_note_holds_is_a_note_lookup(ask, question):
    said = ask(question)[0]
    assert "reporting in" not in said and "assistant" not in said.lower(), said
    assert "Atlas" in said and "Project Atlas" in said, said


@pytest.mark.parametrize(("question", "line"), [
    ("what did I do on 25 October", "- [Felt really good after the run today, 6 km without stopping](#/notes/27)"),
    ("what happened on 9 October", "- [**Movies**](#/notes/18): Watched Arrival on 9 October and liked it a lot."),
])
def test_z28_a_day_question_says_what_the_notes_hold_not_that_they_were_made(ask, question, line):
    said = ask(question)[0]
    assert line in said and "Made the note" not in said, said


def test_z28_a_made_question_still_names_what_was_made(ask):
    assert "Made the note" in ask("what did I make yesterday")[0]


@pytest.mark.parametrize("question", ["what is on saturday", "what is due this week", "what is coming up"])
def test_z43_a_dated_item_that_is_its_title_is_the_link_said_once(ask, question):
    said = ask(question)[0]
    assert "- [Coffee with Anna on Saturday at Brunetti](#/notes/30)" in said, said
    assert "([Coffee with Anna" not in said and "([Remember to pay rent" not in said, said


def test_z43_a_line_under_a_real_title_keeps_both(ask):
    assert "- Dentist appointment on 4 November 2026 at 9:30. ([Dentist](#/notes/13))" in ask("what is on 4 November")[0]


@pytest.mark.parametrize("question", ["what goes in the soup", "lentil soup ingredients", "what are the contents of the lentil soup note"])
def test_z46_a_frame_word_is_not_a_missing_topic(ask, question):
    said = ask(question)[0]
    for word in ("goes", "ingredients", "contents"):
        assert f"“{word}”" not in said, said


@pytest.mark.parametrize("question", ["hello", "hey", "good morning"])
def test_z51_a_greeting_states_only_what_it_counted(ask, question):
    said = ask(question)[0]
    assert "waiting on you" not in said and "That makes" not in said, said
    assert said.count("Weekly review") <= 1 and "writing about weekly" not in said and "about weekly" not in said, said


@pytest.mark.parametrize("question", ["how are you", "yes", "ok"])
def test_z51_a_neutral_turn_is_not_met_as_if_stressed(ask, question):
    said = ask(question)[0]
    assert "most pressing" not in said and "one thing at a time" not in said.lower() and "take it in order" not in said.lower(), said


@pytest.mark.parametrize(("question", "lead"), [
    ("is the passport packed", "Yes, “Passport” is ticked off"),
    ("is the charger packed", "Not yet: “Charger” is still open"),
    ("is everything packed", "Not yet: three of five still open on Lisbon packing list: charger, sunscreen and power adapter."),
    ("what's unpacked", "3 still to do on Lisbon packing list:"),
    ("what is left in my todo", "3 still to do on Todo this week:"),
    ("what do I need to buy", "4 still to do on Shopping list:"),
    ("what have I ticked off", "You have ticked off four items across three notes:"),
])
def test_z56_a_checklist_state_is_one_reader_for_every_phrasing(client, session, monkeypatch, question, lead):
    seed_1030.seed(session)
    said = seed_1030.asker(client, monkeypatch, chat=True)(question)[0]
    assert said.startswith(lead), said
    assert "do not mention" not in said and "general knowledge" not in said, said
