"""INBOX 1461, the owner (Ask, no model, "What have I saved about courses &
study?"): "timing, time words, and phrasing is still off".

Three classes, each tested several ways:

1. A note's own time words ("this week", "today", "last week") are said
   against the day the note was written, in the past tense once that day
   has gone, in the register of the question: the exact date first for
   "when did I" and "what date"; the relative form for a casual question;
   close days relative only. INBOX 1483 (the owner, newer: "it sounds wierd
   and not natural") moved how both are said: the relative time leads and
   the date follows only where it helps ("three weeks ago, on 8 October",
   "back in July"), never "on 8 October (three weeks ago)".
2. A title-less note is named by a clean noun phrase ("your note on design
   class for prototyping"), never "the had design class today ...".
3. A group line names two or three notes, then "and N more"; a count is
   said once; uni notes are never "a hobby forming".

Fixed clock: Friday 30 October 2026, 10:00.
"""

from __future__ import annotations

import contextvars
import datetime as dt
import re
from datetime import date

import pytest

from tessellate.ai import composer_digest, composer_frame, insights
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 30, 10, 0, 0)
TODAY = NOW.date()
D = dt.datetime

NOTES = [
    ("my uni days this week are tuesday and thursday", D(2026, 7, 17, 9)),
    ("I had three lectures for my cloud computing class last week.", D(2026, 7, 26, 9)),
    ("had design class today for prototyping", D(2026, 7, 20, 9)),
    ("# Cloud computing\n\nNotes on cloud computing: IaaS, PaaS and SaaS.", D(2026, 7, 10, 9)),
    ("I just missed the bus to uni today, but I ran into a uni friend.", D(2026, 10, 8, 9)),
]
MORE = [
    ("Studied for the stats exam in the library.", D(2026, 8, 3, 9)),
    ("# Essay plan\n\nIntro, two case studies, counterargument, conclusion.", D(2026, 9, 1, 9)),
    ("Group project meeting moved to Friday.", D(2026, 9, 10, 9)),
    ("# Reading list\n\nMyers chapters 1 to 3, the stats primer.", D(2026, 9, 14, 9)),
    ("Got my results back for the networks quiz: 18 out of 20.", D(2026, 9, 20, 9)),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(notes, question: str) -> str:  # noqa: ANN001
        for text, when in notes:
            entry = manager.create_entry(session, text, category_name="Courses & study", tags=["university"])
            entry.created_at = entry.updated_at = when
        session.commit()
        return _ask(client, question, use_tools=False, notes_only=True, answer_from="notes")["text"]

    return build


# 1. Time words against the note's own day, by the rule table.


def _pinned(question: str, text: str, written: date) -> str:
    #: In a copy of the context: the timing set here never reaches the
    #: next test in this worker (`test_gold_answers` pins against its own day).
    def run() -> str:
        composer_digest._TODAY.set(TODAY)
        composer_digest._set_timing(question)
        return composer_digest._pin(text, written)

    return contextvars.copy_context().run(run)


PLAIN = ["What have I saved about courses & study?", "tell me about uni", "what are my notes on design class",
         "uni", "show me my study notes"]
CASUAL = ["what have I been up to lately", "yooo what's been going on with uni", "what did I do last week",
          "anything new recently", "what did I do the other day", "lol what's up with uni"]
EXACT = ["when did I have design class", "what date was my design class", "when was the bus thing",
         "which day did I miss the bus", "When did I last go to uni?"]


@pytest.mark.parametrize("question", PLAIN)
def test_plain_leads_with_how_far_back(question):
    #: INBOX 1483 moved this intent: was "on 20 July (three months ago)".
    assert _pinned(question, "had design class today for prototyping", date(2026, 7, 20)) == \
        "had design class back in July for prototyping"
    assert _pinned(question, "I missed the bus today", date(2026, 10, 8)) == "I missed the bus three weeks ago, on 8 October"
    #: Close: the relative word alone.
    assert _pinned(question, "I missed the bus today", date(2026, 10, 29)) == "I missed the bus yesterday"


@pytest.mark.parametrize("question", CASUAL)
def test_casual_is_relative_and_distant_by_month(question):
    assert _pinned(question, "had design class today for prototyping", date(2026, 7, 20)) == \
        "had design class back in July for prototyping"
    assert _pinned(question, "I missed the bus today", date(2026, 10, 8)) == "I missed the bus three weeks ago"
    assert _pinned(question, "I missed the bus today", date(2026, 10, 29)) == "I missed the bus yesterday"


@pytest.mark.parametrize("question", EXACT)
def test_when_did_i_gets_the_exact_date_first(question):
    #: Yesterday goes without its date even here: the owner's rule of
    #: 2026-10-31 (composer-1031), "today and yesterday said relatively only".
    assert _pinned(question, "I missed the bus today", date(2026, 10, 29)) == "I missed the bus yesterday"
    #: The date first, then how far back in words (INBOX 1483: never bracketed).
    assert _pinned(question, "I missed the bus today", date(2026, 10, 8)) == "I missed the bus on 8 October, about three weeks ago"
    assert _pinned(question, "had design class today", date(2026, 7, 20)) == "had design class on 20 July, about three months ago"


@pytest.mark.parametrize("question", PLAIN[:2] + CASUAL[:2] + EXACT[:2])
@pytest.mark.parametrize("text", ["I missed the bus today", "I'm at uni tonight", "today was long"])
def test_today_in_todays_note_stays_today(question, text):
    """The relative part is left out when the day is today: the word stays."""
    assert _pinned(question, text, TODAY) == text


@pytest.mark.parametrize("question", PLAIN[:3])
@pytest.mark.parametrize(("text", "said"), [
    #: INBOX 1483: a time months back is said by its month, not "in the week
    #: of 13 July (three months ago)".
    ("my uni days this week are tuesday and thursday", "my uni days back in July were tuesday and thursday"),
    ("the lab is today", "the lab was back in July"),
    ("my shifts this week are long", "my shifts back in July were long"),
])
def test_a_time_gone_by_is_said_in_the_past(question, text, said):
    written = date(2026, 7, 17) if "week" in text else date(2026, 7, 20)
    assert _pinned(question, text, written) == said


@pytest.mark.parametrize(("first", "monday", "back"), [(0, "13 July", "four"), (6, "19 July", "three")])
def test_last_week_counts_from_the_persons_first_day(monkeypatch, first, monday, back):
    """"last week" in a note of Sunday 26 July: the week of 13 July where
    weeks start on Monday, of 19 July where they start on Sunday."""
    monkeypatch.setattr(composer_digest, "_week_first", lambda: first)
    #: Asked "when", so the week is said by its first day (a plain question
    #: says "back in July" since INBOX 1483, which hides the first day).
    said = _pinned("when did I have three lectures", "I had three lectures last week", date(2026, 7, 26))
    #: 109 and 103 days back, rounded as "about" rounds.
    assert said == f"I had three lectures in the week of {monday}, about {back} months ago", said


@pytest.mark.parametrize("question", ["What have I saved about courses & study?", "tell me about courses & study",
                                      "what have I got on courses & study"])
def test_the_owners_question_reads_in_the_past_with_both(ask, question):
    said = ask(NOTES, question)
    #: INBOX 1483 moved this from "In the week of 13 July (three months ago), ...".
    assert "Back in July, your uni days were Tuesday and Thursday." in said, said
    assert "Back in July, you had design class for prototyping." in said, said
    assert not re.search(r"\b(?:this week|today)\b", said), said


# 2. A title-less note by a clean noun phrase.


@pytest.mark.parametrize(("content", "name"), [
    ("had design class today for prototyping", "your note on design class for prototyping"),
    ("went to the gym after work", "your note on the gym after work"),
    ("studied for the exam tonight", "your note on the exam"),
    ("Finished my assignment on networks", "your note on your assignment on networks"),
    ("Started a new job", "your note on a new job"),
    ("Met Sam for coffee yesterday", "your note on Sam for coffee"),
])
def test_a_diary_line_is_named_by_what_it_is_about(content, name):
    assert composer_frame.short_name({"id": 1, "content": content}) == name


@pytest.mark.parametrize("content", ["Advanced calculus", "Grilled cheese recipe", "Weekend plans", "Reading list"])
def test_a_name_that_looks_like_a_past_stays_a_name(content):
    #: Said as it is, with no article (composer-1031: "the Cloud computing").
    assert composer_frame.short_name({"id": 1, "content": content}) == content


@pytest.mark.parametrize(("content", "name"), [
    ("my uni days this week are tuesday and thursday", "the note on your uni days"),
    ("my shifts today are long", "the note on your shifts"),
    ("my readings last week were dense", "the note on your readings"),
])
def test_a_subject_name_drops_its_time_words(content, name):
    assert composer_frame.short_name({"id": 1, "content": content}) == name


@pytest.mark.parametrize("content", ["Group project meeting moved to Friday", "Lab report handed in on Monday",
                                     "Tutorial changed to Thursday"])
def test_a_line_that_says_something_is_never_worn_as_a_title(content):
    named = composer_frame.short_name({"id": 1, "content": content})
    assert not named.startswith(f"the {content}"), named


# 3. A summary, not a list, and a count said once.


def _notes(n: int) -> list[dict]:
    return [{"id": i, "content": f"# Topic {i}\n\nbody", "tags": ["uni"]} for i in range(1, n + 1)]


@pytest.mark.parametrize(("n", "said"), [
    (2, "Topic 1 and Topic 2"),
    (3, "Topic 1, Topic 2 and Topic 3"),
    (4, "Topic 1, Topic 2 and two more"),
    (6, "Topic 1, Topic 2 and four more"),
    (10, "Topic 1, Topic 2 and eight more"),
])
def test_a_group_names_two_or_three_then_counts(n, said):
    notes = _notes(n)
    group = composer_frame.Group(ids=[x["id"] for x in notes], name="uni", joined_by="all tagged #uni", band="closest")
    assert said in composer_frame.group_line(group, notes, "study"), composer_frame.group_line(group, notes, "study")


def test_the_owners_overview_says_each_count_once(ask):
    said = ask(NOTES + MORE, "What have I saved about courses & study?")
    assert said.startswith("You have ten notes about university."), said
    #: Every note shares #university, so no group line lists them; a
    #: group's naming is `test_a_group_names_two_or_three_then_counts`.
    assert said.count("ten notes") == 1, said
    #: The count is not said again as "10 times".
    assert not re.search(r"\b10 times\b", said), said
    assert "the had " not in said and "the Group project meeting" not in said, said


@pytest.mark.parametrize(("texts", "category"), [
    (["Design class today", "Design class again", "Design class on prototyping", "Design class review"], "Courses & study"),
    (["Uni lecture session", "Lecture session two", "Session three of the lecture", "Lecture session four"], ""),
    (["Exam practice", "More exam practice", "Exam practice set", "Exam practice again"], ""),
    (["Client meeting session", "Meeting session again", "Session with the client", "Meeting session four"], ""),
])
def test_study_and_work_are_never_a_hobby_forming(texts, category):
    notes = [{"id": i, "content": t, "category": category, "created_at": f"2026-0{7 + i}-0{1 + i}T09:00:00"}
             for i, t in enumerate(texts)]
    found = insights.recurrence(texts[0].split()[0].lower(), notes, TODAY)
    assert found is None or "hobby" not in found.text, found.text


def test_a_leisure_class_is_still_a_hobby_forming():
    texts = ["Pottery class today", "Pottery class again", "Pottery class glazing", "Pottery class wheel"]
    notes = [{"id": i, "content": t, "created_at": f"2026-0{7 + i}-0{1 + i}T09:00:00"} for i, t in enumerate(texts)]
    found = insights.recurrence("pottery", notes, TODAY)
    assert found is not None and "hobby forming" in found.text, found
