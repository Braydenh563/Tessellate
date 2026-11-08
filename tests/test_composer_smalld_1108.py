"""CHAT_PLAN small rows, batch D (no model, no note): reviewer findings on batch C,
the stale rows, round/min/max/log/pow words, text join/split/count, Unix time.
Fixed clock: Sunday 8 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import commands, composer_chance, composer_epoch, composer_extra, composer_smalltalk, composer_study, composer_sums, composer_text, utilities

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


# --- 2: T1 leftovers as words -----------------------------------------------------------------
SUMS = [
    ("round 3.7", "3.7 rounded is 4."),
    ("round 2.5", "2.5 rounded is 3."),
    ("round 3.14159 to 2 decimal places", "3.14159 rounded to 2 decimal places is 3.14."),
    ("round 2.675 to 2 decimals", "2.675 rounded to 2 decimal places is 2.68."),
    ("what is 3.2 rounded", "3.2 rounded is 3."),
    ("floor 3.7", "3.7 rounded down is 3."),
    ("round down 3.7", "3.7 rounded down is 3."),
    ("what is the floor of -3.2", "-3.2 rounded down is -4."),
    ("ceil 3.2", "3.2 rounded up is 4."),
    ("ceiling of 3.2", "3.2 rounded up is 4."),
    ("round up 3.2", "3.2 rounded up is 4."),
    ("log 100", "The log (base 10) of 100 is 2."),
    ("log of 1000", "The log (base 10) of 1,000 is 3."),
    ("log2 8", "The log (base 2) of 8 is 3."),
    ("log base 2 of 8", "The log (base 2) of 8 is 3."),
    ("ln 1", "The natural log of 1 is 0."),
    ("natural log of 10", "The natural log of 10 is 2.302585."),
    ("pow(2, 10)", "2 to the power of 10 is 1,024."),
    ("pow 2 10", "2 to the power of 10 is 1,024."),
    ("2 to the power of 10", "2 to the power of 10 is 1,024."),
    ("2 raised to 3", "2 to the power of 3 is 8."),
    ("2(3+4)", "2(3+4) is 14."),
    ("what is 2 (3 + 4)", "2 (3 + 4) is 14."),
    ("(1+2)(3+4)", "(1+2)(3+4) is 21."),
    ("3(2)", "3(2) is 6."),
]


@pytest.mark.parametrize("q,start", SUMS)
def test_sum_words(q, start):
    assert said(q).startswith(start), (q, said(q))


@pytest.mark.parametrize("q,why", [
    ("log 0", "not defined"), ("log of -5", "not defined"), ("ln 0", "not defined"), ("log base 1 of 5", "base"), ("log base 0 of 5", "base"),
    ("2 to the power of 10000", "too large"), ("10 to the power of 20", "too large"), ("0 to the power of -1", "cannot"), ("pow(9, 999)", "too large"),
])
def test_sum_words_say_why_when_they_cannot(q, why):
    assert why in said(q), (q, said(q))


@pytest.mark.parametrize("q", [
    "round up my notes on X", "max's birthday", "the log from Tuesday", "log 5 miles in my running note", "floor plan for the house", "ceiling paint note",
    "ln is it", "pow wow notes", "round the clock", "split the trip note", "join the club note", "2 (3 days)", "call 555(1234)", "round 3.7 notes", "log",
])
def test_sum_words_leave_note_questions_alone(q):
    assert composer_sums.answer(ctx(q)) is None, q


def test_sum_words_are_linear_on_long_input():
    import time

    start = time.perf_counter()
    for q in ("round " + "1" * 20000, "log " + " " * 20000 + "5", "(" * 20000, "2" + "(2" * 10000, "pow " + "9 " * 10000):
        composer_sums.answer(ctx(q))
    assert time.perf_counter() - start < 1.0


# --- 3: T6 leftovers on pasted text -----------------------------------------------------------
def test_join_lines_with_commas():
    text = said("join lines with commas:\nmilk\neggs\nbread")
    assert text.startswith("Joined with commas:\n\n```\nmilk, eggs, bread\n```")
    assert "nothing was saved or changed" in text
    assert said("join these lines with commas: milk\neggs") .startswith("Joined with commas:")


def test_split_on_commas_into_lines():
    assert said("split on commas: milk, eggs, bread").startswith("Split into lines:\n\n```\nmilk\neggs\nbread\n```")
    assert said("split this into lines: a, b").startswith("Split into lines:")


def test_count_characters_with_and_without_spaces():
    assert said("count characters: hello there").startswith("11 characters, 10 without spaces.")
    assert said("character count: a b").startswith("3 characters, 2 without spaces.")
    assert said('count the characters "tea time"').startswith("8 characters, 7 without spaces.")
    assert said("count characters: x").startswith("1 character, 1 without spaces.")


@pytest.mark.parametrize("q", [
    "split the trip note", "join the club note", "join the club", "split my notes by topic", "count characters in my notes", "count characters in the passport note",
    "join: ", "split on commas", "character count of my essay note", "join the team note: ok",
])
def test_text_words_do_not_take_note_questions(q):
    assert composer_text.answer(ctx(q)) is None, q


# --- 4: Unix epoch -----------------------------------------------------------------------------
def test_epoch_to_a_date():
    assert said("what is 1700000000 as a date").startswith("1700000000 is Tuesday 14 November 2023, 22:13:20 UTC.")
    assert said("convert unix time 0 to a date").startswith("0 is Thursday 1 January 1970, 00:00:00 UTC.")
    assert "Read as seconds since 1 January 1970 UTC" in said("epoch 1700000000 to date")
    assert said("what date is timestamp 1700000000000").startswith("1700000000000 is Tuesday 14 November 2023, 22:13:20 UTC.")
    assert "milliseconds" in said("what date is timestamp 1700000000000")


def test_unix_time_now_uses_the_clock():
    got = said("unix time now")
    assert got.startswith(f"The Unix time is {int(NOW.timestamp())}.")
    assert said("what is the current epoch time").startswith(f"The Unix time is {int(NOW.timestamp())}.")


def test_a_date_as_unix_time():
    assert said("unix time of 1 January 2024").startswith("1 January 2024 is 1704067200 in Unix time")
    assert said("what is 3 march 2027 in unix time").startswith("3 March 2027 is 1804032000 in Unix time")
    assert said("epoch for 25 december").startswith("25 December 2026 is 1798156800 in Unix time")


@pytest.mark.parametrize("q", [
    "what is unix", "what is epoch", "the unix time of my meeting", "epoch time of my notes", "what is 99999999999999999 as a date", "unix time of the plan",
    "what is 12 as a date", "what is 2024 as a date",
])
def test_epoch_leaves_other_questions_alone(q):
    assert composer_epoch.answer(ctx(q)) is None, q


def test_text_and_epoch_readers_are_linear_on_long_input():
    import time

    start = time.perf_counter()
    for q in ("join lines with commas:" + "a\n" * 9000, "split on commas: " + "a," * 9000, "count characters: " + "a " * 9000, "unix time of " + "1 " * 40, "epoch " + "9" * 5000 + " to date",
              "split " + "the " * 5000 + "note", "unix time of" + " " * 5000 + "x"):
        composer_extra.answer(ctx(q))
    assert time.perf_counter() - start < 1.0


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
