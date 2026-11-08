"""CHAT_PLAN small rows, batch D (no model, no note): reviewer findings on batch C,
the stale rows, round/min/max/log/pow words, text join/split/count, Unix time.
Fixed clock: Sunday 8 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import commands, composer_chance, composer_extra, composer_smalltalk, composer_study, composer_text, utilities

NOW = dt.datetime(2026, 11, 8, 10, 0, 0)


def ctx(q: str, **extra) -> composer_study.Ctx:
    return composer_study.Ctx(question=q, notes=extra.pop("notes", []), now=NOW, seed="s", asked=q, **extra)


def said(q: str) -> str:
    reply = composer_extra.answer(ctx(q))
    return reply.text if reply else ""


# --- 0a: case transforms leave note words alone ---------------------------------------------
@pytest.mark.parametrize("q", [
    "uppercase my notes about X", "title case the plan", "lowercase my reminders", "uppercase the passport note",
    "slugify my tasks", "make my entries lowercase", "title case my list",
])
def test_case_transforms_do_not_take_note_questions(q):
    assert composer_text.answer(ctx(q)) is None


@pytest.mark.parametrize("q,out", [
    ('uppercase "my notes"', "MY NOTES"), ("uppercase: the plan", "THE PLAN"), ("title case: my reminders list", "My Reminders List"),
    ("uppercase hello there", "HELLO THERE"),
])
def test_case_transforms_with_pasted_text_still_run(q, out):
    assert out in said(q)


# --- 0b: pick is narrow ---------------------------------------------------------------------
@pytest.mark.parametrize("q", ["pick up milk or eggs from the store", "choose a title and a color", "choose a/b", "select all or none", "decide what to wear"])
def test_pick_leaves_ordinary_sentences_alone(q):
    assert composer_chance.answer(ctx(q)) is None


@pytest.mark.parametrize("q", ["pick tea or coffee", "pick pizza, sushi, tacos", "choose from red, green, blue", "decide between a and b", "pick among x/y/z"])
def test_pick_still_reads_option_lists(q):
    assert composer_chance.answer(ctx(q)) is not None


# --- 0c: a bare day and month in a week question is this year -------------------------------
def test_week_of_a_past_date_stays_this_year():
    assert "week 10 of 2026" in said("what week is 3 March")
    assert "2027" not in said("what week is 3 March")
    assert "week 10 of 2026" in said("what week is March 3rd")


def test_week_of_a_future_date_and_a_named_year():
    assert "week 52 of 2026" in said("what week is 25 December")
    assert "week 9 of 2027" in said("what week is 3 March 2027")


def test_day_of_year_of_a_date():
    assert "day 62 of 2026" in said("what day of the year is 3 March")


# --- 0d: fractions to two decimals ----------------------------------------------------------
def test_a_third_is_two_decimals():
    assert said("a third of 10").startswith("A third of 10 is 3.33.")
    assert said("a third of 100").startswith("A third of 100 is 33.33.")


# --- 1: rows the plan still lists as open, asked in the plan's own phrasing ------------------
PASSPORT = {"id": 7, "title": "Passport", "content": "# Passport\n" + "renew the passport before travel " * 20, "category": "Life", "tags": []}


def _utility(q: str) -> str:
    got = utilities.answer(q, NOW, "s")
    return " ".join(str(part) for row in (got or []) for part in row)


@pytest.mark.parametrize("q,needle", [("roll 2d6", "in all"), ("flip a coin", ""), ("roll a dice", ""), ("pick a number between 1 and 10", "1")])
def test_t11_dice_and_coin_answer(q, needle):
    got = _utility(q)
    assert got and needle in got


def test_t5_word_count_and_reading_time_of_a_named_note():
    for q in ("how many words is the passport note", "reading time of the passport note", "how many words in the passport note"):
        reply = composer_extra.answer(ctx(q, notes=[PASSPORT]))
        assert reply is not None and "word" in reply.text and "Passport" in reply.text, (q, reply)


def test_c6_identity_names_atlas():
    assert composer_smalltalk.social_kind("who are you") == "who"
    assert all("Atlas" in line for line in composer_smalltalk.SOCIAL["who"])


@pytest.mark.parametrize("q,intent", [
    ("file this under Work", "move"), ("pin this", "pin"), ("pin the passport note", "pin"), ("delete the passport note", "delete"),
    ("make a note: buy milk", "new_note"), ("open the passport note", "open"), ("link A and B", "link"),
])
def test_x_verbs_read_as_their_acts(q, intent):
    found = commands.read_typed(q, NOW)
    assert found is not None and found["intent"] == intent
