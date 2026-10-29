"""Value slots, verb and noun pairs, counts and ages (audit 1029 ranks 18 and 19,
C21, C23, C34): the sentence that answers must hold the slot the question asks
for (a number with a unit, a date), and when none does the answer says so and
names the nearest note. One slot table serves every question, so each case
here runs over several subjects. No model, in Ask and in Chat.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
from datetime import date

import pytest

from tessellate.ai import composer, composer_slots
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime
TODAY = date(2026, 10, 29)


@pytest.fixture
def notebook(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(notes):
        for text, when, *tags in notes:
            entry = manager.create_entry(session, text, "Personal", tags=tags[0] if tags else None)
            entry.created_at = entry.updated_at = when
        session.commit()

        def go(question: str, chat: bool = False) -> str:
            kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
            return _ask(client, question, **kw)["text"]

        return go

    return build


MODES = pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
NOISE = (
    "# Shopping\n\nBuy milk and eggs. The sale ends soon.",
    D(2026, 10, 22, 9),
)


def _does_not_say(said: str) -> bool:
    return "do not say" in said.lower() or "does not say" in said.lower()


# --- 1. value slots ---------------------------------------------------------------------


@MODES
@pytest.mark.parametrize(
    ("dish", "temp", "phrasing"),
    [
        ("sourdough", "230C", "what temperature do I bake at"),
        ("sourdough", "230C", "what temperature do I bake the sourdough at"),
        ("focaccia", "200C", "what temperature do I bake the focaccia at"),
        ("scones", "180C", "what temperature should I bake scones at"),
    ],
)
def test_temperature_answers_with_the_degrees(notebook, dish, temp, phrasing, chat):
    notes = [
        (f"# Baking notes\n\nI like to bake bread on Sundays. Bake the {dish} at {temp} for 40 minutes.", D(2026, 10, 20, 9)),
        NOISE,
    ]
    said = notebook(notes)(phrasing, chat)
    assert temp in said, said
    assert "milk" not in said.lower(), said


@MODES
def test_temperature_with_no_degrees_says_so_and_cites_the_nearest(notebook, chat):
    notes = [("# Baking notes\n\nI bake sourdough on Sundays. The crust was great.", D(2026, 10, 20, 9)), NOISE]
    said = notebook(notes)("what temperature do I bake at", chat)
    assert _does_not_say(said), said
    assert "baking notes" in said.lower(), said
    assert "milk" not in said.lower(), said


@MODES
@pytest.mark.parametrize(
    ("thing", "phrasing"),
    [("race", "when is the race"), ("beta", "what is the beta date"), ("exam", "when is the exam"), ("wedding", "what is the wedding date")],
)
def test_when_answers_with_a_date(notebook, thing, phrasing, chat):
    notes = [
        (f"# {thing.capitalize()}\n\nThe {thing} makes me nervous. The {thing} is on 14 November at 9am.", D(2026, 10, 20, 9)),
        NOISE,
    ]
    said = notebook(notes)(phrasing, chat)
    assert "14 November" in said, said
    assert "milk" not in said.lower(), said


@MODES
@pytest.mark.parametrize(("thing", "phrasing"), [("race", "when is the race"), ("beta", "what is the beta date")])
def test_when_with_no_date_says_so_and_cites_the_nearest(notebook, thing, phrasing, chat):
    notes = [(f"# {thing.capitalize()} plan\n\nTrain hard for the {thing}. Sleep well.", D(2026, 10, 20, 9)), NOISE]
    said = notebook(notes)(phrasing, chat)
    assert _does_not_say(said), said
    assert f"{thing} plan" in said.lower(), said
    assert "milk" not in said.lower(), said


@MODES
@pytest.mark.parametrize(
    ("unit", "other", "phrasing"),
    [
        ("km", "5 km", "how many km did I run on Sunday"),
        ("miles", "3 miles", "how many miles did I run on Sunday"),
        ("pages", "40 pages", "how many pages did I read on Sunday"),
    ],
)
def test_how_many_answers_with_the_number_and_unit(notebook, unit, other, phrasing, chat):
    verb = "read" if unit == "pages" else "ran"
    notes = [
        (f"# Log\n\nOn Saturday I {verb} {other}.\n\nOn Sunday I went out early. On Sunday I {verb} 12 {unit} and felt fine.", D(2026, 10, 26, 9)),
        NOISE,
    ]
    said = notebook(notes)(phrasing, chat)
    assert f"12 {unit}" in said, said
    assert "milk" not in said.lower(), said


@MODES
def test_how_many_with_no_number_says_so(notebook, chat):
    notes = [("# Log\n\nI went for a long run on Sunday and felt fine.", D(2026, 10, 26, 9)), NOISE]
    said = notebook(notes)("how many km did I run on Sunday", chat)
    assert _does_not_say(said), said
    assert "milk" not in said.lower(), said


def test_the_slot_table_reads_each_kind_by_one_reader():
    kinds = {slot.kind for slot in composer_slots.SLOTS}
    assert {"temperature", "date", "quantity"} <= kinds
    assert composer_slots.read_value("temperature", "Bake at 230C for an hour") == "230C"
    assert composer_slots.read_value("temperature", "Bake at 230 degrees") == "230 degrees"
    assert composer_slots.read_value("temperature", "Bake for 40 minutes") is None
    assert composer_slots.read_value("quantity", "Ran 12 km today", "km") == "12 km"
    assert composer_slots.read_value("quantity", "Ran 12 kilometres today", "km") == "12 kilometres"
    assert composer_slots.read_value("quantity", "Ran for 40 minutes", "km") is None


def test_questions_that_are_not_value_slots_are_left_alone():
    notes = [{"id": 1, "content": "# Todo\n\n- [x] Pay rent", "created_at": "2026-10-24T09:00:00"}]
    views = [composer.read_note(n, i) for i, n in enumerate(notes)]

    class Out:
        lines: list = []
        rows: list = []

    for q in ["how many notes do I have", "what is the capital of France", "when I was young", "how many apples are in a pie"]:
        assert composer_slots.answer(Out(), q, views, TODAY) is False, q


# --- 2. verbs and nouns -----------------------------------------------------------------


@MODES
@pytest.mark.parametrize(
    ("noun", "phrasing"),
    [("Flight", "when do I fly"), ("Trip", "when do I travel"), ("Departure", "when do I depart")],
)
def test_a_verb_finds_the_note_that_says_it_as_a_noun(notebook, noun, phrasing, chat):
    notes = [(f"# {noun} to Lisbon\n\nBooked for 14 November, early morning.", D(2026, 10, 20, 9)), NOISE]
    said = notebook(notes)(phrasing, chat)
    assert "14 November" in said, said
    assert "milk" not in said.lower(), said


def test_the_verb_noun_pairs_are_synonyms():
    from tessellate.ai import composer_tables

    assert len(composer_tables.VERB_NOUN_PAIRS) >= 20
    for pair in composer_tables.VERB_NOUN_PAIRS:
        verb, *nouns = pair
        for noun in nouns:
            assert composer._stem(noun) in composer._alternatives(composer._stem(verb)), (verb, noun)


@MODES
@pytest.mark.parametrize(
    ("question", "note"),
    [
        ("when do I cook for the party", "# Recipe night\n\nCook for the party. The big recipe is on 14 November."),
        ("when do I register", "# Registration\n\nThe form is due on 14 November."),
        ("when do I renew", "# Renewal\n\nPassport due on 14 November."),
        ("when do I vote", "# Election\n\nBallot day is 14 November."),
    ],
)
def test_other_verbs_find_their_nouns(notebook, question, note, chat):
    said = notebook([(note, D(2026, 10, 20, 9)), NOISE])(question, chat)
    assert "14 November" in said and "milk" not in said.lower(), said


# --- 3. how often, how old ----------------------------------------------------------------


@MODES
@pytest.mark.parametrize("topic", ["baking", "running", "chess"])
def test_how_often_counts_the_notes_tagged_or_titled(notebook, topic, chat):
    notes = [
        (f"# {topic.capitalize()} log one\n\nFirst session went fine.", D(2026, 10, 20, 9)),
        (f"# {topic.capitalize()} log two\n\nSecond session went fine.", D(2026, 10, 22, 9)),
        (f"# Weekend\n\nSaw friends. A little {topic} too.", D(2026, 10, 25, 9), [topic]),
        (f"# Errands\n\nBought a tin of paint, some string and a lot of {topic} gear.", D(2026, 10, 23, 9)),
        NOISE,
    ]
    said = notebook(notes)(f"how often do I write about {topic}", chat)
    assert "3 notes" in said or "three notes" in said.lower(), said
    assert "milk" not in said.lower(), said


@MODES
def test_how_often_with_nothing_filed_says_so(notebook, chat):
    notes = [("# Errands\n\nBought a tin of paint and some baking powder.", D(2026, 10, 23, 9)), NOISE]
    said = notebook(notes)("how often do I write about baking", chat)
    assert "no note is titled or tagged baking" in said.lower(), said


@MODES
def test_how_often_i_do_a_thing_counts_the_notes_filed_under_it(notebook, chat):
    notes = [
        ("# Running log\n\nEasy 5 km.", D(2026, 10, 20, 9)),
        ("# Running log two\n\nLong 10 km.", D(2026, 10, 24, 9)),
        ("# Shopping\n\nNew running socks.", D(2026, 10, 22, 9)),
    ]
    said = notebook(notes)("how often do I run", chat)
    assert "2 notes" in said and "socks" not in said.lower(), said


@MODES
@pytest.mark.parametrize(
    ("what", "started", "age"),
    [("sourdough starter", "1 September 2026", "58 days"), ("kombucha", "9 October 2026", "20 days")],
)
def test_how_old_reads_the_start_date(notebook, what, started, age, chat):
    notes = [(f"# {what.capitalize()}\n\nStarted on {started}. Feed it daily.", D(2026, 10, 27, 9)), NOISE]
    said = notebook(notes)(f"how old is my {what}", chat)
    assert age in said, said


@MODES
def test_how_old_with_no_start_date_says_so(notebook, chat):
    notes = [("# Sourdough starter\n\nFeed it daily. It smells fine.", D(2026, 10, 27, 9)), NOISE]
    said = notebook(notes)("how old is my sourdough starter", chat)
    assert _does_not_say(said), said
