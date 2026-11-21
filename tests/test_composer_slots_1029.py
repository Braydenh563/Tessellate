"""Slot-first answers (audit 1029 C22, C23, C33; INBOX 1357: the class).

The item that answers a question must hold the question's slot: a ticked or
unticked task for "did I pay X", the open tasks of the named list for "what is
left on X", a dated line that says the thing for "how long since I called
mum", the note titled as the subject for "how long until the dentist". When
no note holds the slot the answer says so and never offers a near item. Each
case runs over several subjects and phrasings, in Ask and in Chat, no model.

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
BILLS = ["electricity", "water", "internet"]
PLACES = ["dentist", "optician", "vet"]


def _todo(bill: str, place: str):
    return [
        (f"# Todo\n\n- [x] Pay the {bill} bill\n- [ ] Book the {place} follow-up\n- [ ] Buy a capo", D(2026, 10, 24, 9)),
        ("# Songs\n\nLearn the new chorus. Buy a capo for the guitar.", D(2026, 10, 20, 9)),
    ]


@MODES
@pytest.mark.parametrize("bill", BILLS)
@pytest.mark.parametrize("phrasing", ["did I pay the {b} bill", "have I paid the {b} bill", "did I already pay the {b} bill"])
def test_a_ticked_task_answers_yes(notebook, bill, phrasing, chat):
    said = notebook(_todo(bill, "dentist"))(phrasing.format(b=bill), chat)
    assert said.lower().startswith("yes"), said
    assert "capo" not in said.lower(), said


@MODES
@pytest.mark.parametrize("place", PLACES)
@pytest.mark.parametrize("phrasing", ["have I booked the {p} follow-up", "did I book the {p} follow-up"])
def test_an_unticked_task_answers_not_yet(notebook, place, phrasing, chat):
    said = notebook(_todo("water", place))(phrasing.format(p=place), chat)
    assert said.lower().startswith("not yet"), said
    assert "capo" not in said.lower(), said


@MODES
@pytest.mark.parametrize("thing", ["gas bill", "car insurance", "boiler service"])
def test_no_note_holds_the_slot_so_the_answer_says_so(notebook, thing, chat):
    said = notebook(_todo("water", "vet"))(f"did I pay the {thing}", chat)
    assert "found nothing" in said.lower(), said
    assert "capo" not in said.lower(), said


def _trip(place: str):
    return [
        (f"# {place} packing list\n\n- [x] Passport\n- [ ] Charger\n- [ ] Sunscreen", D(2026, 10, 20, 9)),
        ("# Attendees\n\n- [ ] Sara\n- [ ] Tom\n- [ ] Priya", D(2026, 10, 13, 9)),
    ]


@MODES
@pytest.mark.parametrize("place", ["Lisbon", "Porto", "Oslo"])
@pytest.mark.parametrize("phrasing", ["what is left on the {p} packing list", "what is left on {p} packing list", "what is still left on the {p} packing list"])
def test_left_lists_the_open_items_of_the_named_list(notebook, place, phrasing, chat):
    said = notebook(_trip(place))(phrasing.format(p=place), chat)
    assert "Charger" in said and "Sunscreen" in said, said
    assert "Passport" not in said and "Sara" not in said and "Save it" not in said, said


@MODES
@pytest.mark.parametrize("phrasing", ["what is left on the {p} packing list", "what do I still need to bring for {p}"])
def test_left_on_a_list_nobody_made_says_so(notebook, phrasing, chat):
    said = notebook(_trip("Lisbon"))(phrasing.format(p="Tokyo"), chat)
    assert "Sara" not in said and "Charger" not in said and "Save it" not in said, said
    assert "no checklist" in said.lower() or "none of them covers it" in said.lower(), said


def _calls(who: str, other: str):
    return [
        (f"# Calls\n\nCalled {who} on 24 October. Long chat about the garden.", D(2026, 10, 24, 9)),
        (f"# Todo\n\n- [ ] Call {other}", D(2026, 10, 26, 9)),
    ]


@MODES
@pytest.mark.parametrize(("who", "other"), [("mum", "dad"), ("Sam", "Alex"), ("grandma", "Jo")])
def test_how_long_since_counts_from_the_dated_line(notebook, who, other, chat):
    said = notebook(_calls(who, other))(f"how long since I called {who}", chat)
    assert "5 days ago" in said, said


@MODES
@pytest.mark.parametrize(("who", "other"), [("mum", "dad"), ("Sam", "Alex"), ("grandma", "Jo")])
def test_how_long_since_an_open_todo_does_not_count(notebook, who, other, chat):
    said = notebook(_calls(who, other))(f"how long since I called {other}", chat)
    assert "do not say" in said and "days ago" not in said, said


@MODES
@pytest.mark.parametrize("place", PLACES)
@pytest.mark.parametrize("phrasing", ["how long until the {p}", "how many days until the {p}"])
def test_until_uses_the_note_titled_as_the_subject(notebook, place, phrasing, chat):
    notes = [
        (f"# Call the {place}\n\nCall the {place} tomorrow.", D(2026, 10, 28, 9)),
        (f"# {place.capitalize()}\n\nAppointment on 4 November at 9am.", D(2026, 10, 22, 9)),
    ]
    said = notebook(notes)(phrasing.format(p=place), chat)
    assert "4 November" in said and "today" not in said.lower().split("4 november")[0], said


@MODES
def test_until_a_day_no_note_holds_says_so(notebook, chat):
    said = notebook(_todo("water", "vet"))("how long until the tax return", chat)
    assert any(w in said.lower() for w in ("no day", "found no", "none of them covers it")), said


def _pairs(dish: str, count: int):
    notes = [
        (f"# {dish} one\n\nThe first {dish} used red lentils and a long simmer.", D(2026, 10, 20, 9)),
        (f"# {dish} two\n\nThe second {dish} used green lentils, short simmer, plus a lot of extra detail here.", D(2026, 10, 21, 9)),
        ("# Shopping\n\nBuy milk.", D(2026, 10, 22, 9)),
    ]
    return notes[:count] + notes[2:]


@MODES
@pytest.mark.parametrize("dish", ["lentil soup", "bean chilli", "tomato curry"])
@pytest.mark.parametrize("phrasing", ["compare the two {d} notes", "compare my two {d} notes"])
def test_compare_the_two_notes_answers_both_sides(notebook, dish, phrasing, chat):
    said = notebook(_pairs(dish, 2))(phrasing.format(d=dish), chat)
    assert "red lentils" in said and "green lentils" in said, said


@MODES
@pytest.mark.parametrize("dish", ["lentil soup", "bean chilli", "tomato curry"])
def test_compare_with_one_side_missing_says_which(notebook, dish, chat):
    said = notebook(_pairs(dish, 1))(f"compare the two {dish} notes", chat)
    assert "only one" in said.lower() and "milk" not in said.lower(), said


# --- the reader, unit level ---------------------------------------------------------


def _views(notes: list[dict]):
    return [composer.read_note(n, i) for i, n in enumerate(notes)]


class _Out:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.rows: list = []


def test_questions_that_are_not_slots_are_left_alone():
    notes = [{"id": 1, "content": "# Todo\n\n- [x] Pay rent", "created_at": "2026-10-24T09:00:00"}]
    for q in ["what is in my todo", "summarise my notes", "what is the capital of France", "did the game finish"]:
        assert composer_slots.answer(_Out(), q, _views(notes), TODAY) is False, q


@pytest.mark.parametrize("pattern", [composer_slots._DID, composer_slots._LEFT, composer_slots._NEED, composer_slots._SINCE])
@pytest.mark.parametrize("text", ["did i " + "a " * 30000, "what is left" + " " * 50000 + "x", "how long since i " * 5000, "what do i " + "need to " * 8000])
def test_slot_patterns_stay_linear(pattern, text):
    import time

    start = time.perf_counter()
    pattern.match(text)
    assert time.perf_counter() - start < 0.2
