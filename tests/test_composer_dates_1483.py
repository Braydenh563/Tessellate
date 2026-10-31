"""INBOX 1483, the owner (Ask, no model): "I still dont like how ot refers to
dates, it sounds wierd and not natural when I read it". The screenshot read
"On 8 October (three weeks ago), you missed the bus to uni ... chill :D,¹
from one of your notes.", "University is a regular subject of yours
(confirmed by you, 11 October).", and the chips "What's the latest on
university friend?".

The class, not the case: every day the composer says reads as a person says
it. The relative time leads and the date follows only where it helps
("Three weeks ago, on 8 October", "Back in July", "On Tuesday", "Yesterday");
"when did I" keeps the date first in words ("On 8 October, about three weeks
ago"); never a bracketed distance after a date; a learned fact says who said
it as a person would; no ", from one of your notes" tail; a chip names its
subject in the person's own words.

Fixed clock: Friday 30 October 2026 (weeks start on Monday).
"""

from __future__ import annotations

import contextvars
import datetime as dt
import re
from datetime import date

import pytest

from tessellate.ai import composer_digest, insights
from tessellate.api import routes_chat

TODAY = date(2026, 10, 30)


@pytest.fixture(autouse=True)
def _monday_first(monkeypatch):
    monkeypatch.setattr(composer_digest, "_week_first", lambda: 0)


def _said(question: str, text: str, written: date) -> str:
    #: In a copy of the context: the timing set here never reaches the
    #: next test in this worker (`test_gold_answers` pins against its own day).
    def run() -> str:
        composer_digest._TODAY.set(TODAY)
        composer_digest._set_timing(question)
        return composer_digest._pin(text, written)

    return contextvars.copy_context().run(run)


# Six question shapes, each by its register.
PLAIN = "tell me about the bus"
CASUAL = "yooo what's up with the bus"
WHEN = "when did I miss the bus"
WHAT_DATE = "what date did I miss the bus"
HOW_LONG = "how long ago did I miss the bus"
THEIR_WEEK = "what did I do last week"

# The note's day: today, yesterday, earlier this week, last week, months ago.
DAYS = {"today": date(2026, 10, 30), "yesterday": date(2026, 10, 29), "this week": date(2026, 10, 27),
        "last week": date(2026, 10, 20), "months ago": date(2026, 7, 20)}

BUS = "you missed the bus"
SAID = {
    (PLAIN, "today"): f"{BUS} today",
    (PLAIN, "yesterday"): f"yesterday, {BUS}",
    (PLAIN, "this week"): f"on Tuesday, {BUS}",
    (PLAIN, "last week"): f"a week ago, on 20 October, {BUS}",
    (PLAIN, "months ago"): f"back in July, {BUS}",
    (CASUAL, "today"): f"{BUS} today",
    (CASUAL, "yesterday"): f"yesterday, {BUS}",
    (CASUAL, "this week"): f"on Tuesday, {BUS}",
    (CASUAL, "last week"): f"a week ago, {BUS}",
    (CASUAL, "months ago"): f"back in July, {BUS}",
    (WHEN, "today"): f"{BUS} today",
    (WHEN, "yesterday"): f"yesterday, {BUS}",
    (WHEN, "this week"): f"on Tuesday 27 October, {BUS}",
    (WHEN, "last week"): f"on 20 October, about a week ago, {BUS}",
    (WHEN, "months ago"): f"on 20 July, about three months ago, {BUS}",
    (WHAT_DATE, "today"): f"{BUS} today",
    (WHAT_DATE, "yesterday"): f"yesterday, {BUS}",
    (WHAT_DATE, "this week"): f"on Tuesday 27 October, {BUS}",
    (WHAT_DATE, "last week"): f"on 20 October, about a week ago, {BUS}",
    (WHAT_DATE, "months ago"): f"on 20 July, about three months ago, {BUS}",
    (HOW_LONG, "today"): f"{BUS} today",
    (HOW_LONG, "yesterday"): f"yesterday, {BUS}",
    (HOW_LONG, "this week"): f"three days ago, on Tuesday 27 October, {BUS}",
    (HOW_LONG, "last week"): f"a week ago, on 20 October, {BUS}",
    (HOW_LONG, "months ago"): f"three months ago, on 20 July, {BUS}",
    (THEIR_WEEK, "today"): f"{BUS} today",
    (THEIR_WEEK, "yesterday"): f"yesterday, {BUS}",
    (THEIR_WEEK, "this week"): f"on Tuesday, {BUS}",
    (THEIR_WEEK, "last week"): f"last week, {BUS}",
    (THEIR_WEEK, "months ago"): f"back in July, {BUS}",
}


@pytest.mark.parametrize(("question", "day"), list(SAID))
def test_a_day_reads_as_a_person_says_it(question, day):
    said = _said(question, "you missed the bus today", DAYS[day])
    assert said == SAID[question, day], said


@pytest.mark.parametrize(("question", "day"), list(SAID))
def test_never_a_bracketed_distance_after_a_date(question, day):
    for text in ("you missed the bus today", "had design class today for prototyping",
                 "my uni days this week are tuesday and thursday", "I had three lectures last week"):
        said = _said(question, text, DAYS[day])
        assert "(" not in said and not re.search(r"\d \w+ \(", said), said


@pytest.mark.parametrize("question", [PLAIN, WHEN, HOW_LONG])
def test_a_date_said_inside_a_sentence_closes_its_aside(question):
    """"had design class three weeks ago, on 8 October, for prototyping":
    the aside's second comma, before the words go on."""
    said = _said(question, "had design class today for prototyping", date(2026, 10, 8))
    assert re.search(r"8 October, (?:about three weeks ago, )?for prototyping$", said), said


@pytest.mark.parametrize("question", [PLAIN, CASUAL, THEIR_WEEK])
def test_a_distant_week_is_back_in_its_month(question):
    #: Said in the second person by then (`_second_person` runs first).
    said = _said(question, "your uni days this week are tuesday and thursday", date(2026, 7, 17))
    assert said == "back in July, your uni days were tuesday and thursday", said


# The owner's notebook, end to end through the digest.

NOTES = [
    {"id": 1, "content": "I just missed the bus to uni today, but I ran into a uni friend and met her friend as well so it was chill :D",
     "created_at": "2026-10-08T09:00:00", "tags": ["university"], "category": "Courses & study"},
    {"id": 2, "content": "had design class today for prototyping", "created_at": "2026-07-20T09:00:00",
     "tags": ["university"], "category": "Courses & study"},
    {"id": 3, "content": "my uni days this week are tuesday and thursday", "created_at": "2026-07-17T09:00:00",
     "tags": ["university"], "category": "Courses & study"},
]


def _answer(question: str) -> dict:
    return composer_digest.answer(question, NOTES, today=TODAY)


@pytest.mark.parametrize("question", ["what about my uni friend", "tell me about my uni friend", "anything on my uni friend"])
def test_the_owners_line_reads_naturally(question):
    said = _answer(question)["text"]
    assert said.startswith("Three weeks ago, on 8 October, you missed the bus to uni, but you ran into a uni friend"), said
    #: The diary's ":D" is an emoji, dropped like one; no tail after the mark.
    assert ":D" not in said and "from one of your notes" not in said, said


@pytest.mark.parametrize(("question", "lead"), [
    ("when did I miss the bus", "On 8 October, about three weeks ago, you missed the bus to uni"),
    ("how long ago did I miss the bus", "Three weeks ago, on 8 October, you missed the bus to uni"),
    ("tell me about uni", "Back in July, your uni days were Tuesday and Thursday."),
])
def test_each_register_end_to_end(question, lead):
    said = _answer(question)["text"]
    assert lead in said, said
    assert not re.search(r"\((?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+) \w+ ago\)", said), said
    assert "months from now" not in said and "Your back" not in said, said


# Chips: the subject in the person's own words.


@pytest.mark.parametrize(("topic", "question", "said"), [
    ("university friend", "who is my uni friend", "my uni friend"),
    ("uni friend", "what about my uni friend", "my uni friend"),
    ("university friend", "uni friend", "my uni friend"),
    ("miss bus", "when did I miss the bus", "the bus"),
    ("see university friend", "did I see my uni friend", "my uni friend"),
    ("friend university", "what happened with my friend at uni", "my friend at uni"),
    ("uni", "tell me about uni", "uni"),
    ("dentist", "when is the dentist", "the dentist"),
    ("Project Atlas", "what about project atlas", "Project Atlas"),
])
def test_a_chip_names_its_subject_in_the_persons_words(topic, question, said):
    assert composer_digest._chip_subject(topic, question) == said


@pytest.mark.parametrize("question", ["what about my uni friend", "anything on my uni friend"])
def test_the_owners_chips_read(question):
    chips = _answer(question)["next"]
    assert chips and all("university friend" not in c for c in chips), chips
    assert any("my uni friend" in c for c in chips), chips


def test_when_chips_never_name_the_verb():
    chips = _answer("when did I miss the bus")["next"]
    assert not any("miss bus" in c for c in chips), chips
    assert any(c.endswith("about the bus?") or c.endswith("on the bus?") for c in chips), chips


# A learned fact, said as a person says who told it.


@pytest.mark.parametrize(("said", "on", "line"), [
    ("University is a regular subject of yours", date(2026, 10, 11),
     "University is a regular subject of yours, as you told me on 11 October."),
    ("Golf is a hobby of yours", date(2026, 3, 2), "Golf is a hobby of yours, as you told me on 2 March."),
    ("You write about running every week.", date(2026, 10, 29), "You write about running every week, as you told me on 29 October."),
])
def test_a_confirmed_fact_says_who_told_it(said, on, line):
    assert insights.confirmed_line(said, on) == line
    assert "(" not in line


@pytest.mark.parametrize(("stored", "now"), [
    ("University is a regular subject of yours (confirmed by you, 11 October).",
     "University is a regular subject of yours, as you told me on 11 October."),
    ("Golf is a hobby of yours (confirmed by you, 6 October).", "Golf is a hobby of yours, as you told me on 6 October."),
    ("Golf is a hobby of yours, as you told me on 6 October.", "Golf is a hobby of yours, as you told me on 6 October."),
])
def test_a_line_confirmed_before_is_said_in_todays_words(stored, now):
    assert insights._said_now(stored) == now


# The model path's hints: data for the model, never a bracketed distance.


class _Entry:
    def __init__(self, created):
        self.created_at = created
        self.edited_at = None


@pytest.mark.parametrize("created", [dt.datetime(2026, 10, 30, 9), dt.datetime(2026, 10, 29, 9),
                                     dt.datetime(2026, 10, 20, 9), dt.datetime(2026, 7, 20, 9)])
def test_the_model_hints_never_bracket_a_distance(created):
    written = routes_chat._note_dates(_Entry(created), dt.UTC)
    assert "(" not in written and re.match(r"\w+day \d{1,2} \w+ 2026, \d\d:\d\d$", written), written

    class Said:
        phrase, at, precision = "today", created, "day"

    worded = routes_chat._time_words([Said], TODAY)[0]
    assert "(" not in worded and re.search(r"2026, (?:today|yesterday|\d+ days ago)$", worded), worded
