"""Readers and comparisons of the chat plan (ledger 1112): L105, L-chat-6, L209. No model, fixed day."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import composer, composer_extra, composer_study

TODAY = dt.date(2026, 11, 10)


def _note(i: int, content: str, day: str) -> dict:
    return {"id": i, "content": content, "category": "Work", "tags": [], "created_at": f"{day}T10:00:00Z"}


NOTES = [
    _note(1, "Release alpha\nShip on 3 December 2026.", "2026-10-01"),
    _note(2, "Release beta\nShip on 20 December 2026.", "2026-10-05"),
    _note(3, "Release gamma\nShip on 11 January 2027.", "2026-10-09"),
    _note(6, "Shopping\n- [ ] milk\n- [ ] eggs", "2026-09-01"),
    _note(7, "Todo\n- [ ] call dentist", "2026-10-02"),
]


def lead(question: str) -> str:
    return composer.compose(question, NOTES, today=TODAY)["text"].split("\n")[0]


@pytest.mark.parametrize("question", [
    "which of alpha, beta and gamma is the newest", "which of alpha, beta or gamma is newest",
    "which of the Release alpha, beta and gamma notes is the newest",
])
def test_l105_which_of_three_names_is_the_newest(question):
    text = lead(question)
    assert text.startswith("**Release gamma** is the newest:"), text
    assert "5 October" in text and "1 October" in text, text


def test_l105_the_oldest_of_three_and_the_first_of_three_trips():
    assert lead("which of alpha, beta or gamma is the oldest").startswith("**Release alpha** is the oldest:")
    assert lead("which of alpha, beta and gamma comes first").startswith("**Release alpha** comes first:")


def test_l105_two_names_after_of_still_compare():
    assert lead("which of Release alpha or Release beta is newer").startswith("**Release beta** is newer:")


def test_l105_a_question_with_no_names_is_not_a_comparison():
    assert not lead("which of my notes is the newest").startswith("**")


@pytest.mark.parametrize("question", ["which is oldest, Shopping or Todo", "which is the oldest, Shopping or Todo"])
def test_l_chat_6_two_list_notes_are_compared_by_their_days(question):
    text = lead(question)
    assert text.startswith("**Shopping** is the oldest: 1 September against 2 October for **Todo**"), text


def test_l209_who_is_older_reads_a_birth_year_and_an_age():
    notes = [_note(4, "Anna\nAnna was born in 1990. Gift: scarf.", "2026-10-01"), _note(5, "Tom\nTom is 41. Gift: book", "2026-10-02")]
    ctx = composer_study.Ctx(question="who is older, Anna or Tom", notes=notes, now=dt.datetime(2026, 11, 10, 10), seed="s", asked="who is older, Anna or Tom")
    assert composer_extra.answer(ctx).text == "Tom is older: 41 against born 1990 for Anna."


# --- the route: the seeded notebook (a Todo note, dentist, passport, Atlas) --------

import tests._seed_1031c as seed_c  # noqa: E402


@pytest.fixture
def go(client, session, monkeypatch):
    from datetime import datetime

    from tessellate.entry import manager

    seed_c.seed(session)
    entry = manager.create_entry(session, "# Shopping\n\n- [ ] milk\n- [ ] eggs", category_name="Home", tags=[])
    entry.created_at = entry.updated_at = datetime.fromisoformat("2026-09-01T10:00:00")
    session.commit()
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("question", ["which is oldest, Shopping or Todo", "which is the oldest, Shopping or Todo"])
def test_l_chat_6_shopping_or_todo_is_a_date_comparison_not_the_checklist(go, question):
    text = go(question)[0]
    assert text.startswith("**Shopping** is the oldest: 1 September against 26 October for **Todo**"), text


@pytest.mark.parametrize("question", [
    "which is the oldest, the dentist, the passport renewal or the atlas beta",
    "which of the dentist, the passport renewal and the atlas beta is the oldest",
])
def test_l_chat_5_three_notes_with_little_in_common_are_all_compared(go, question):
    text = go(question)[0]
    assert text.startswith("**Passport** is the oldest: 12 October against 15 October for **Project Atlas** and 18 October for **Dentist**"), text
    assert "nothing mentions" not in text, text


def test_l_chat_9_and_a_statement_is_not_a_swap():
    from tessellate.ai import composer_dialogue

    for said in ("and I went home", "and then it rained", "and the dentist said hello to me"):
        assert composer_dialogue._swap_reading(said, "when is the passport renewal") is composer_dialogue._NOT_THIS, said  # noqa: SLF001
    assert composer_dialogue._swap_reading("and the dentist", "when is the passport renewal").question.lower().startswith("when is the dentist")  # noqa: SLF001


def test_l_chat_14_the_only_list_with_an_intro_line_is_shown_for_what_is_on_my_list():
    from tests.test_composer_r3_1107 import say

    todo = "# Todo\n\nThings I need to do before Friday.\n\n- [ ] Book MOT\n- [ ] Email landlord"
    for question in ("what is on my list", "what's on the list"):
        said = say(question, todo, "Dentist on 11 November")
        assert "Book MOT" in said and "Email landlord" in said and "couldn't find" not in said, said
    assert say("what is on my list", todo, "# Packing\n\nFor the trip.\n\n- [ ] Passport\n- [ ] Charger") == "Which list: Todo or Packing?"


@pytest.mark.parametrize("day", [dt.date(2026, 11, 9), dt.date(2026, 11, 12), dt.date(2026, 11, 15)])
def test_l33_last_week_is_the_previous_monday_to_sunday_in_every_reader(day):
    from tessellate.ai import recognise_windows
    from tessellate.entry import timewords
    from tessellate.search import query

    now = dt.datetime(day.year, day.month, day.day, 10)
    mon, sun = dt.date(2026, 11, 2), dt.date(2026, 11, 8)
    asked = query.understand("what did I write last week", now)
    assert (asked.since, asked.until) == (mon, sun)
    assert recognise_windows.span("last week", day)[:2] == (mon, sun)
    assert recognise_windows.window("last week", now) == (dt.datetime(2026, 11, 2), dt.datetime(2026, 11, 8, 23, 59, 59))
    assert timewords.find("last week", now)[0].at == mon


# --- L213: the probe's time-window rows (Tuesday 2026-10-06), the reader ratchet at zero ----

PROBE_NOW = dt.datetime(2026, 10, 6, 10, 0)


@pytest.mark.parametrize(("phrase", "first", "last"), [
    ("yesterday", dt.date(2026, 10, 5), dt.date(2026, 10, 5)), ("a week ago", dt.date(2026, 9, 29), dt.date(2026, 9, 29)),
    ("3 weeks ago", dt.date(2026, 9, 15), dt.date(2026, 9, 15)), ("the week before last", dt.date(2026, 9, 21), dt.date(2026, 9, 27)),
    ("since march", dt.date(2026, 3, 1), dt.date(2026, 10, 6)), ("in march", dt.date(2026, 3, 1), dt.date(2026, 3, 31)),
    ("last friday", dt.date(2026, 10, 2), dt.date(2026, 10, 2)),
])
def test_l213_the_past_is_a_window(phrase, first, last):
    from tessellate.ai import recognise_windows

    got = recognise_windows.window(phrase, PROBE_NOW)
    assert (got[0].date(), got[1].date()) == (first, last), got


@pytest.mark.parametrize(("phrase", "wanted"), [
    ("last friday", dt.datetime(2026, 10, 2, 9)), ("the 21st", dt.datetime(2026, 10, 21, 9)), ("21st of next month", dt.datetime(2026, 11, 21, 9)),
    ("end of the month", dt.datetime(2026, 10, 31, 9)), ("mid november", dt.datetime(2026, 11, 15, 9)), ("in a fortnight", dt.datetime(2026, 10, 20, 9)),
    ("christmas", dt.datetime(2026, 12, 25, 9)), ("later today", dt.datetime(2026, 10, 6, 13)), ("in 6 months", dt.datetime(2027, 4, 6, 10)),
    ("pay rent on the 1st", dt.datetime(2026, 11, 1, 9)), ("dentist 21st 9am", dt.datetime(2026, 10, 21, 9)),
])
def test_l213_a_day_in_words_resolves_against_the_clock(phrase, wanted):
    from tessellate.ai import when

    assert when.resolve(phrase, PROBE_NOW) == wanted


def _dentist(day: str) -> dict:
    return _note(9, f"Dentist appointment\nOn {day}.", "2026-10-01")


@pytest.mark.parametrize("question", ["how long since the dentist", "how long until the dentist"])
def test_l221_a_day_gone_by_is_said_once_and_a_wrong_way_question_still_answers(question):
    text = composer.compose(question, [_dentist("9 November 2026")], today=TODAY)["text"].split("\n")[0]
    assert text.startswith("One day ago, on 9 November"), text
    assert "yesterday" not in text.lower() and "figure you noted" not in text, text


def test_l221_a_day_ahead_asked_with_since_still_answers():
    text = composer.compose("how long since the dentist", [_dentist("17 November 2026")], today=TODAY)["text"].split("\n")[0]
    assert text.startswith("Seven days from today, on 17 November"), text


def test_l104_compare_two_notes_gives_a_side_by_side_table():
    notes = [
        _note(11, "Lisbon trip\nFlights cost 120 euros. Leave on 20 November 2026.", "2026-10-01"),
        _note(12, "Tokyo trip\nFlights cost 640 euros. Leave on 3 December 2026.", "2026-10-06"),
    ]
    text = composer.compose("compare Lisbon and Tokyo", notes, today=TODAY)["text"]
    lines = [ln for ln in text.split("\n") if ln.startswith("|")]
    assert lines and lines[0].startswith("| | Lisbon | Tokyo |"), text
    labels = [ln.split("|")[1].strip() for ln in lines[2:]]
    assert "Price" in labels and "Next day" in labels, text
