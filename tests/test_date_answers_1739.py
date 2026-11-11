"""INBOX 1739: the date answers (composer, with and without a model).

The owner asked "What did I write on 3 November?" and then "any other notes
around that time". Fixed clock: Tuesday 10 November 2026, 09:00. The notebook:
"Uni is done!! :D" written Tuesday 3 November (its text says "on friday",
which the timeline files under Friday 30 October), a golf note on 2 November,
a gym note on 4 November, a mermaid document on 3 November and an older
"Current Commitments" note.
"""

from __future__ import annotations

from datetime import date, datetime

import re

import pytest

from tessellate.ai import composer_aware, composer_intent, composer_shift
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core import clock
from tessellate.core.database import Document
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 10, 9, 0)
UNI_BODY = "Just finished my final assignment on friday at 3:30am but it's done haha!"
FIRST = "What did I write on 3 November?"
THEN = "any other notes around that time"
TYPO = "any othjer notes around that time"


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    #: The follow-ups read their day against this clock (`composer_dialogue`), not the config's.
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


@pytest.fixture
def notebook(session):
    rows = [
        (f"Uni is done!! :D\n\n{UNI_BODY}", "2026-11-03T10:00"),
        ("Golf\n\nPlayed 18 holes at the club and shot 92.", "2026-11-02T10:00"),
        ("Gym\n\nLeg day with squats and lunges.", "2026-11-04T10:00"),
        ("Current Commitments\n\nWork shifts and uni deadlines this month.", "2026-10-20T10:00"),
    ]
    for content, made in rows:
        entry = manager.create_entry(session, content)
        entry.created_at = entry.updated_at = datetime.fromisoformat(made)
        session.commit()
        #: The timeline's rule reads the day a phrase meant, against the day the note was written.
        manager.record_dates(session, entry, now=entry.created_at)
    session.add(Document(title="Untitled document 2", content="graph TD\n  A --> B", created_at=datetime(2026, 11, 3, 19, 49)))
    session.commit()


def _two_turns(client):
    first = _ask(client, FIRST, history=[])
    second = _ask(client, THEN, history=[{"question": FIRST, "answer": first["text"]}])
    return first["text"], second["text"]


# (e) the closing line never names a month for a day, and is English

def test_a_date_question_leaves_its_day_as_the_chat_topic():
    history = [{"question": FIRST, "answer": "You wrote one note on 3 November: it said so."}]
    assert chat_said._chat_topic(history) == "3 November"  # noqa: SLF001


@pytest.mark.parametrize("question", ["what did I do last week", "what did I write on Friday", "notes from October"])
def test_a_date_word_alone_is_never_the_topic(question):
    history = [{"question": question, "answer": f"{question}: you wrote notes in October, on Friday, last week."}]
    assert chat_said._chat_topic(history) not in {"October", "Friday", "week", "November"}  # noqa: SLF001


@pytest.mark.parametrize("topic", ["3 November", "last week", "golf", "Sara"])
@pytest.mark.parametrize("seed", [str(i) for i in range(12)])
def test_the_resume_line_is_english_and_says_the_topic(topic, seed):
    line = composer_aware.closing(composer_aware.build(topic=topic), seed, asked="and what about them?")
    assert "pull the notes on it up" not in line and not re.search(r"We were on (?!the subject)", line)
    assert topic in line


# (a) the answer and the timeline file a note under the same day

def test_the_timeline_files_the_uni_note_under_friday(notebook, client):
    rows = client.get("/timeline", params={"start": "2026-10-29T00:00:00", "end": "2026-11-05T23:59:59"}).json()["rows"]
    uni = next(r for r in rows if r["key"] == "note:1")
    assert uni["bucket"] == "2026-10-30" and uni["written_at"].startswith("2026-11-03")


def test_the_date_answer_says_both_days_when_the_timeline_files_it_elsewhere(client, notebook):
    said = _ask(client, FIRST, history=[])["text"]
    assert "written 3 november, about friday 30 october" in said.lower(), said


def test_a_note_the_timeline_files_on_its_written_day_says_one_day(client, notebook):
    said = _ask(client, "What did I write on 2 November?", history=[])["text"]
    assert "Golf" in said and "(2 November)" in said and "about" not in said, said


# (c) a short personal note is quoted as written, its title once

def test_a_short_personal_note_is_quoted_not_retold(client, notebook):
    said = _ask(client, FIRST, history=[])["text"]
    #: The note has no heading, so it is its words: quoted whole, once, not named and then repeated.
    assert f"“Uni is done!! :D {UNI_BODY}”" in said, said
    assert "your final assignment" not in said
    assert said.count("Uni is done") == 1, said


def test_a_headed_short_note_is_quoted_without_its_title_repeated(client, session):
    entry = manager.create_entry(session, "# Run done\n\nI ran 5 km before work and my knee felt fine.")
    entry.created_at = entry.updated_at = datetime(2026, 11, 3, 10, 0)
    session.commit()
    said = _ask(client, FIRST, history=[])["text"]
    assert "“I ran 5 km before work and my knee felt fine.”" in said and said.count("Run done") == 1, said


def test_an_untitled_short_note_is_quoted_once_under_its_day(client, session):
    entry = manager.create_entry(session, "Booked my dentist for the 21st and told my mum.")
    entry.created_at = entry.updated_at = datetime(2026, 11, 3, 10, 0)
    session.commit()
    said = _ask(client, FIRST, history=[])["text"]
    assert said.count("Booked my dentist") == 1 and "“Booked my dentist for the 21st and told my mum.”" in said, said


def test_a_long_note_is_still_retold_in_the_second_person(client, session):
    body = " ".join(f"I went to the shop number {n} and I bought my bread there." for n in range(1, 8))
    entry = manager.create_entry(session, f"Shopping\n\n{body}")
    entry.created_at = entry.updated_at = datetime(2026, 11, 3, 10, 0)
    session.commit()
    said = _ask(client, FIRST, history=[])["text"]
    assert f"“{body}”" not in said, said


# (b) documents made on the day count too, named as documents

def test_the_day_counts_its_documents_too(client, notebook):
    said = _ask(client, FIRST, history=[])["text"]
    assert "Untitled document 2" in said and "one document" in said, said
    assert said.startswith("You wrote one note and made one document on 3 November"), said


def test_a_day_with_only_a_document_is_the_documents(client, session):
    session.add(Document(title="Quarter plan", content="Goals", created_at=datetime(2026, 11, 3, 8, 0)))
    session.commit()
    said = _ask(client, FIRST, history=[])["text"]
    assert "Quarter plan" in said and "document" in said and "note" not in said.split("\n")[0], said


def test_a_document_on_another_day_is_not_counted(client, notebook):
    said = _ask(client, "What did I write on 4 November?", history=[])["text"]
    assert "Untitled document 2" not in said and "Gym" in said, said


# model on and off give the same facts (CHAT_PLAN decision 75)

def _prompt(fake) -> str:
    rounds = [*fake.chat_calls[-1:], *fake.tool_rounds[-1:]]
    return "\n".join(str(m.get("content") or "") for messages in rounds for m in messages)


def test_a_model_is_handed_the_same_facts_for_the_day(ai_client, fake_ollama, notebook):
    _ask(ai_client, FIRST, use_tools=False, history=[])
    sent = _prompt(fake_ollama)
    assert "Untitled document 2" in sent, sent[-900:]
    assert UNI_BODY in sent and "Friday 30 October" in sent, sent[-900:]


# (d) "around that time" after a date answer carries the date

@pytest.mark.parametrize("asked", [
    "any other notes around that time", "what else around then", "anything near then",
    "other notes near that time", "and around that time?", "what about around then", "any more notes close to then",
])
def test_a_near_follow_up_is_read_as_the_days_around_the_last_one(asked):
    got = composer_shift.follow(asked, FIRST, {}, date(2026, 11, 10))
    assert got is not None and "around 3 November" in got, (asked, got)


@pytest.mark.parametrize("asked", ["what time is it", "any other notes", "around the corner", "notes about then and now", "what did I write on friday"])
def test_a_question_that_is_not_a_near_follow_up_is_left_alone(asked):
    assert composer_shift.follow(asked, FIRST, {}, date(2026, 11, 10)) is None


def test_around_a_day_is_three_days_either_side():
    plan = composer_intent.plan("what else did I write around 3 November", date(2026, 11, 10))
    assert plan.kind == "recall" and plan.window == (date(2026, 10, 31), date(2026, 11, 6))
    assert plan.around == date(2026, 11, 3) and plan.others
    plain = composer_intent.plan("what did I write on 3 November", date(2026, 11, 10))
    assert plain.window == (date(2026, 11, 3), date(2026, 11, 3)) and plain.around is None


def test_the_follow_up_answers_with_the_notes_either_side_nearest_first(client, notebook):
    first, second = _two_turns(client)
    assert "I found no mention" not in second, second
    assert "Golf" in second and "Gym" in second, second
    assert "2 November" in second and "4 November" in second, second
    assert "Uni is done" not in second and "Untitled document 2" not in second and "Current Commitments" not in second, second
    assert "nearest first" in second and "within three days of 3 November" in second, second


def test_the_nearest_day_comes_first(client, notebook, session):
    for content, made in [("Dentist\n\nCheck-up and a clean.", "2026-11-06T09:00"), ("Haircut\n\nTrimmed the sides.", "2026-11-01T09:00")]:
        entry = manager.create_entry(session, content)
        entry.created_at = entry.updated_at = datetime.fromisoformat(made)
    session.commit()
    _, second = _two_turns(client)
    far = [second.index("Dentist"), second.index("Haircut")]
    assert max(second.index("Golf"), second.index("Gym")) < min(far), second
    assert second.index("Haircut") < second.index("Dentist"), second


def test_the_owners_typo_is_read_as_the_near_follow_up(client, notebook):
    first = _ask(client, FIRST, history=[])["text"]
    second = _ask(client, TYPO, history=[{"question": FIRST, "answer": first}])["text"]
    assert "Golf" in second and "Gym" in second and "I found no mention" not in second, second


def test_a_near_question_with_no_turn_before_asks_nothing_odd(client, notebook):
    said = _ask(client, THEN, history=[])["text"]
    assert "We were on November" not in said


def test_a_model_is_handed_the_notes_either_side_too(ai_client, fake_ollama, notebook):
    first = _ask(ai_client, FIRST, use_tools=False, history=[])
    _ask(ai_client, THEN, use_tools=False, history=[{"question": FIRST, "answer": first["text"]}])
    sent = _prompt(fake_ollama)
    assert "Played 18 holes" in sent and "Leg day" in sent, sent[-1200:]
