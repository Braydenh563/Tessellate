"""The composer-r6 leftovers (composer-r7): a bare lower-case pair ("tom and
sara") is two subjects, and "put it in my journal" is a note called that when
one exists, else today's note. Seed: `tests/_seed_1031c.py`."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import composer_ask, starter_acts


@pytest.mark.parametrize("said, sides", [("tom and sara", ("tom", "sara")), ("lisbon and tokyo", ("lisbon", "tokyo")), ("Tom and Sara", ("Tom", "Sara"))])
def test_a_bare_pair_in_lower_case_is_two_sides(said, sides):
    composer_ask.NOTE_WORDS.set(frozenset({"tom", "sara", "lisbon", "tokyo", "salt", "pepper"}))
    assert composer_ask.compare_sides(said) == sides


@pytest.mark.parametrize("said, known", [("tom and sara", {"tom"}), ("salt and pepper", set())])
def test_a_pair_the_notes_do_not_hold_is_one_thing(said, known):
    composer_ask.NOTE_WORDS.set(frozenset(known))
    assert composer_ask.compare_sides(said) is None


@pytest.mark.parametrize("said", ["black and white", "you and me", "yes and no", "up and down"])
def test_everyday_pairs_stay_one_thing(said):
    composer_ask.NOTE_WORDS.set(frozenset({"black", "white", "you", "yes", "down"}))
    assert composer_ask.compare_sides(said) is None


def test_the_answer_has_a_block_for_each(client, session, monkeypatch):
    seed_c.seed(session)
    text, _ = seed_c.asker(client, monkeypatch)("tom and sara")
    assert "**Tom**" in text and "**Sara**" in text, text


@pytest.mark.parametrize("said", ["put it in my journal", "put buy milk in my journal", "add walked far to my diary"])
def test_my_journal_is_a_starter_act(said):
    kind, slots = starter_acts.read(said)
    assert kind == "append_today" and slots["own"] in {"journal", "diary"}


def test_with_no_journal_note_it_is_today_s_note(client, session, monkeypatch):
    seed_c.seed(session)
    text, events = seed_c.asker(client, monkeypatch, chat=True)("put buy milk in my journal")
    card = next(e for e in events if e.get("type") == "act")
    assert "today's note" in card["label"], card


def test_a_note_called_journal_takes_the_line(client, session, monkeypatch):
    seed_c.seed(session)
    note = client.post("/entries", json={"content": "# Journal\n\nMonday: long walk"}).json()["id"]
    text, events = seed_c.asker(client, monkeypatch, chat=True)("put buy milk in my journal")
    card = next(e for e in events if e.get("type") == "act")
    step = card["steps"][0]
    assert step["name"] == "edit_note" and step["arguments"]["note_id"] == note and "Buy milk" in step["arguments"]["content"], card


def test_a_pointer_with_a_journal_note_asks_for_the_words(client, session, monkeypatch):
    seed_c.seed(session)
    client.post("/entries", json={"content": "# Journal\n\nMonday: long walk"})
    text, _ = seed_c.asker(client, monkeypatch, chat=True)("put it in my journal")
    assert "Say what to add" in text, text
