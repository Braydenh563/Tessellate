"""L-chat-122 (T8): counters. "add 1 to coffee" waits for Confirm and writes one
dated line on the note "Counter: coffee" (made the first time); "how many
coffees this week" sums those lines over the window and says which note it read.
Over the real route, fixed clock (Monday 9 November 2026), no model."""

import pytest

import tests._seed_r9_1109 as sd
from tests._consent import confirmed
from tessellate.ai import composer_counter
from tessellate.core.database import Entry
from sqlalchemy import select


@pytest.fixture
def chat(client, session, monkeypatch):
    sd.fix_clock(monkeypatch)

    def say(question, press=False):
        out = sd.ask(client, question, notes_only=False)
        out = {**out, "act": [e for e in out["events"] if e.get("type") == "act"]}
        return confirmed(client, out) if press else out

    return say


def _counter_note(session):
    session.expire_all()
    return next((e for e in session.scalars(select(Entry)).all() if (e.content or "").startswith("# Counter: ")), None)


def test_adding_waits_for_confirm_then_makes_the_note_with_a_dated_line(chat, session):
    out = chat("add 1 to coffee")
    assert out["act"] and not out["act"][0].get("done") and _counter_note(session) is None
    chat("add 1 to coffee", press=True)
    assert _counter_note(session).content == "# Counter: coffee\n\n- 2026-11-09: +1"


def test_a_second_add_is_a_second_line_and_the_count_reads_back(chat, session):
    chat("add 1 to coffee", press=True)
    chat("count 2 coffees", press=True)
    assert _counter_note(session).content.count("+") == 2
    said = chat("how many coffees this week")["text"]
    assert said.startswith("3 coffees") and "Counter: coffee" in said
    assert chat("how many coffees today")["text"].startswith("3 coffees")
    assert chat("how many coffees last week")["text"].startswith("0 coffees")


@pytest.mark.parametrize("said", ["add 2 to the shopping list", "add milk to my list"])
def test_a_list_is_not_a_counter(said):
    assert composer_counter.read(said) is None


def test_names_and_numbers_read_the_ways_people_say_them():
    for said, n in (("add one to my coffee counter", 1), ("+3 coffee", 3), ("count another coffee", 1), ("tally two coffees", 2)):
        assert composer_counter.read(said) == {"intent": "counter", "name": "coffee", "shown": composer_counter.read(said)["shown"], "n": n}
