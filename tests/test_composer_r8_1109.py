"""Composer round 8 leftovers: a checklist note of named items is made (not answered as banana
bread), a bare "call Anna" is a to-do act offer (a reminder asking when), a pair that sits in one
note as a phrase stays one subject ("salt and pepper"), and the below-the-floor rule (INBOX 1705
e) keeps a loosely related group that holds no word of the question out of the answer.
Seed: `tests/_seed_1031c.py`; the clock is fixed there."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import commands, composer_ask, composer_digest_lines
from tessellate.entry import manager

NOW = seed_c.NOW


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch, chat=True)


# --- a checklist note of named items ---------------------------------------------------

@pytest.mark.parametrize("said", [
    "make a checklist note of milk, eggs and bread",
    "create a checklist of milk, eggs and bread",
    "make me a shopping list with milk, eggs and bread",
    "start a to-do list: milk, eggs, bread",
])
def test_a_checklist_note_is_read_with_its_items(said):
    found = commands.read(said, NOW)
    assert found and found["intent"] == "new_note", found
    lines = [x for x in found["content"].split("\n") if x.startswith("- [ ] ")]
    assert lines == ["- [ ] Milk", "- [ ] Eggs", "- [ ] Bread"], found


@pytest.mark.parametrize("said", ["make a list of my notes", "make a checklist note about the trip", "what is on my shopping list"])
def test_other_asks_are_not_a_new_checklist(said):
    found = commands.read(said, NOW)
    assert not found or "- [ ]" not in str(found.get("content")), found


def test_the_answer_makes_the_checklist_note(go):
    text, events = go("make a checklist note of milk, eggs and bread")
    assert "banana" not in text.lower(), text
    card = next(e for e in events if e.get("type") == "act")
    content = card["steps"][0]["arguments"]["content"]
    assert card["steps"][0]["name"] == "create_note"
    assert all(f"- [ ] {item}" in content for item in ("Milk", "Eggs", "Bread")), card
    assert "#" not in text.split("\n")[0], text


# --- a bare imperative to a person -------------------------------------------------------

@pytest.mark.parametrize("said, task", [("call Anna", "Call Anna"), ("ring Sam", "Ring Sam"), ("text Mum", "Text Mum"), ("call mum", "Call mum"), ("email Anna Smith", "Email Anna Smith")])
def test_a_bare_imperative_to_a_person_is_a_reminder(said, task):
    found = commands.read(said, NOW)
    assert found and found["intent"] == "reminder" and found["text"] == task and not found["time_given"], found


@pytest.mark.parametrize("said", ["call this note Budget", "call the dentist", "call it Budget", "call me back", "call Anna and Tom about the trip"])
def test_other_calls_are_not_the_person_offer(said):
    found = commands.read(said, NOW)
    assert not found or found["intent"] != "reminder" or said.startswith("call the"), found


def test_call_anna_asks_when_and_is_not_a_digest(go):
    text, _ = go("call Anna")
    low = text.lower()
    assert "remind" in low and "anna" in low and "notes about" not in low and "loosely" not in low, text


# --- a pair that is one phrase in a note --------------------------------------------------

@pytest.fixture
def held():
    """Sets the notes' words and texts for one test, and puts them back."""
    tokens = []

    def hold(texts):
        tokens.append((composer_ask.NOTE_WORDS, composer_ask.NOTE_WORDS.set(frozenset({"salt", "pepper"}))))
        tokens.append((composer_ask.NOTE_TEXTS, composer_ask.NOTE_TEXTS.set(texts)))

    yield hold
    for var, token in reversed(tokens):
        var.reset(token)


def test_a_pair_said_together_in_one_note_is_one_subject(held):
    held(("season with salt and pepper to taste.",))
    assert composer_ask.compare_sides("salt and pepper") is None


def test_a_pair_the_notes_hold_apart_is_still_two(held):
    held(("buy salt for the bread.", "pepper plant needs water."))
    assert composer_ask.compare_sides("salt and pepper") == ("salt", "pepper")


def test_the_answer_for_a_recipe_phrase_is_one_search(client, session, monkeypatch):
    """Measured: without the phrase rule the pair is read as two sides and the answer is the
    compare layout ("[**Seasoning**]" citation); with it, one search, said from the note."""
    seed_c.seed(session)
    manager.create_entry(session, "# Seasoning\n\nSeason the stew with thyme and rosemary, then simmer.", category_name="Recipes")
    session.commit()
    text, _ = seed_c.asker(client, monkeypatch)("thyme and rosemary")
    assert "from your Seasoning note" in text and "[**Seasoning**]" not in text, text


# --- INBOX 1705 (e): below the floor -------------------------------------------------------

HOMEWORK = "alright, uhh, I think i wrote a note about eating my homework to smth, it was a joke"


@pytest.fixture
def homework(client, session, monkeypatch):
    """Three notes go together (#joke); the seed's scarecrow joke and Meeting note come as loose
    padding that holds no word of the question."""
    seed_c.seed(session)
    for content, category in [
        ("# Eating my homework\n\nWhy did the student eat his homework? Because the teacher said it was a piece of cake.", "Fun"),
        ("something -> found it during school and thought the website was funny.", "Fun"),
        ("Homework: I ate my homework to something funny, a joke at school.", "Diary"),
    ]:
        manager.create_entry(session, content, category_name=category, tags=["joke"])
    session.commit()
    return seed_c.asker(client, monkeypatch)


def test_a_loose_group_without_a_word_of_the_question_is_left_out(homework):
    text, _ = homework(HOMEWORK)
    assert "scarecrow" not in text and "Meeting" not in text, text
    assert "homework" in text.lower() and "More loosely related" not in text, text


def test_the_floor_is_what_keeps_it_out(homework, monkeypatch):
    """Without the rule the padding is in the answer, so the test above is not vacuous."""
    monkeypatch.setattr(composer_digest_lines, "_below_the_floor", lambda *a, **k: False)
    text, _ = homework(HOMEWORK)
    assert "scarecrow" in text or "Meeting" in text, text
