"""The app's own records, asked in words (CHAT_PLAN A3).

"What did I search yesterday", "what ran overnight", "when did I last back
up": answered from History, the job records and the backup folder, with
times on the person's clock, never searched for in the notes. The phrasings
are tests/fixtures/composer/records_1011.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tessellate.ai import records
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)

EVAL = json.loads((Path(__file__).parent / "fixtures/composer/records_1011.json").read_text(encoding="utf-8"))
ZONE = ZoneInfo("Australia/Perth")
#: Sunday 11 October 2026, 10:30 in Perth.
NOW = datetime(2026, 10, 11, 10, 30, tzinfo=ZONE)


def _utc(month: int, day: int, hour: int, minute: int) -> datetime:
    """A stored instant: naive UTC, as the tables keep it."""
    return datetime(2026, month, day, hour, minute, tzinfo=ZONE).astimezone(timezone.utc).replace(tzinfo=None)


TURNS = [
    (_utc(10, 11, 9, 14), "how's the gym going?"),
    (_utc(10, 10, 22, 40), "what do I need to buy?"),
    (_utc(10, 10, 11, 2), "what have I saved about courses & study?"),
    (_utc(10, 8, 15, 0), "who is Sam?"),
]
RUNS = [
    {"kind": "backup", "label": "Backup", "ran": True, "status": "ok", "finished_at": _utc(10, 11, 3, 0).isoformat(), "result": "Backed up 20 notes"},
    {"kind": "night-shift", "label": "Night shift", "ran": True, "status": "ok", "finished_at": _utc(10, 11, 2, 10).isoformat(), "result": "Derived 14 facts from 80 notes"},
    {"kind": "reindex", "label": "Search index rebuild", "ran": True, "status": "failed", "finished_at": _utc(10, 10, 23, 5).isoformat(), "error": "Disk full"},
    {"kind": "export", "label": "Notebook export", "ran": False, "status": "never"},
]
BACKUPS = [{"name": f"memorymap-{i}.db", "created_at": _utc(10, 11 - i, 3, 0).replace(tzinfo=timezone.utc).isoformat()} for i in range(3)]


def _say(question: str, **records_kw) -> str:
    kw = {"turns": TURNS, "runs": RUNS, "finished": [], "backups": BACKUPS} | records_kw
    found = records.answer(question, None, now=NOW, **kw)
    assert found is not None, question
    return found.text


@pytest.mark.parametrize("kind", ["searches", "ran", "backup"])
def test_every_phrasing_is_read_as_its_record(kind):
    missed = [q for q in EVAL[kind] if records.asks(q) != kind]
    assert missed == []


@pytest.mark.parametrize("question", EVAL["not_records"])
def test_a_notes_question_or_a_how_to_is_not_a_record(question):
    assert records.asks(question) is None


def test_searches_yesterday_are_listed_oldest_first_with_their_times():
    text = _say("what did I search yesterday")
    assert text.startswith("Yesterday, you asked two things in Ask:")
    assert "**11:02:** What have I saved about courses & study?\n\n**22:40:** What do I need to buy?" in text
    assert text.endswith("\n\nOpen History to read their answers?")


def test_a_question_asked_again_is_said_once_with_how_many_times():
    again = [(_utc(10, 11, 9, m), "how's the gym going?") for m in (20, 15)] + TURNS
    text = _say("what did I search today", turns=again)
    assert text.startswith("Today, you asked one question in Ask, three times:")
    assert "**09:20:** How's the gym going? (three times)" in text


def test_a_busy_day_lists_the_latest_eight():
    busy = [(_utc(10, 11, 8, m), f"question {m}?") for m in range(20, 0, -1)]
    text = _say("what did I search today", turns=busy)
    assert text.startswith("Today, you asked 20 things in Ask; the latest eight:")
    assert text.count("**08:") == 8 and "**08:20:** Question 20?" in text and "Question 12?" not in text


def test_the_last_search_is_one_line_with_its_day():
    assert _say("what was my last search").startswith('Your last question in Ask was "How\'s the gym going?", at 09:14 today.')


def test_a_weekday_is_said_as_the_day_it_meant():
    assert _say("what did I ask on Thursday").startswith("On Thursday 8 October, you asked one thing in Ask:")
    assert "You asked nothing in Ask on Monday 5 October." in _say("what did I search on Monday")


def test_overnight_names_its_hours_and_says_what_failed():
    text = _say("what ran overnight")
    assert text.startswith("Overnight, from 18:00 yesterday to 09:00 today, three things ran, and one failed.")
    assert "**23:05 yesterday:** Search index rebuild, failed: disk full." in text
    assert "**02:10 today:** Night shift, done: derived 14 facts from 80 notes." in text
    #: A job that never ran is not listed as having run.
    assert "export" not in text


def test_nothing_ran_says_the_last_thing_that_did():
    text = _say("what ran this morning", runs=RUNS[2:])
    assert text.startswith("Nothing ran this morning. The last thing that ran was the search index rebuild")
    assert "at 23:05 yesterday (failed)." in text


def test_the_task_history_and_the_job_record_count_one_ending_once():
    finished = [{"kind": "backup", "label": "Backup", "outcome": "completed", "detail": "", "at": _utc(10, 11, 3, 0).replace(tzinfo=timezone.utc).isoformat()}]
    assert _say("what ran overnight", finished=finished).count("Backup, done") == 1


def test_the_last_backup_has_its_time_its_age_and_how_many_are_kept():
    text = _say("when did I last back up")
    assert text.startswith("Your last backup was at 03:00 today, seven hours ago. Three backups are kept.")
    assert text.endswith("Open Backups in Settings?")


def test_a_failed_try_after_the_last_backup_is_said():
    failed = [{"kind": "backup", "label": "Backup", "ran": True, "status": "failed", "finished_at": _utc(10, 11, 4, 0).isoformat(), "error": "Disk full."}]
    assert "The try after it, at 04:00 today, failed: Disk full." in _say("is my notebook backed up", runs=failed)


def test_no_backup_says_so():
    assert _say("when was my last backup", backups=[], runs=[]).startswith("There is no backup yet.")


def test_no_questions_yet_says_so():
    assert "nothing in History" in _say("what did I search today", turns=[])


def test_records_answers_keep_the_house_style():
    for question in EVAL["searches"] + EVAL["ran"] + EVAL["backup"]:
        text = _say(question)
        assert chr(0x2014) not in text and "!" not in text, question


def test_through_the_route_the_records_answer_without_search(client, session):
    from tessellate.core.database import AskTurn

    session.add(AskTurn(question="what have I saved about courses & study?", answer="...", created_at=SUITE_NOW.replace(tzinfo=None)))
    session.commit()
    body = {"question": "what did I search today", "history": [], "notes_only": True, "use_tools": False, "answer_from": "notes"}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert "What have I saved about courses & study?" in text
    offer = next(e["offer"] for e in events if e.get("type") == "offer")
    assert offer["surface"] == "ask-history"
