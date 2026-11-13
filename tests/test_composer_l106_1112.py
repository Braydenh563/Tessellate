"""L106 (composer round 4 leftovers, 2026-11-12): R3-18 a "what time" ask, E23 one provenance
per answer, E17 the real route reads a log's yearless date against the edit."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.entry import manager
from tests import _r5_1108 as r5


@pytest.fixture
def ask(client, session, monkeypatch):
    return r5.driver(client, session, monkeypatch)


def test_r3_18_what_time_is_answered_like_when_and_says_a_missing_time(ask):
    said = ask("what time is the dentist")["text"]
    assert "in 4 days" in said and "written back" not in said, said
    assert "gives the day but no time" in said, said


def test_r3_18_a_note_with_a_clock_time_leads_with_it(ask, session):
    manager.create_entry(session, "# Eye test\n\nEye test on 20 November 2026 at 14:30 with Dr Shah.", category_name="Uncategorised")
    session.commit()
    said = ask("what time is the eye test")["text"]
    assert "14:30" in said and "no time" not in said, said


@pytest.mark.parametrize("question", ["when is the dentist appointment", "what time is my dentist appointment"])
def test_e23_an_opener_that_names_the_note_is_not_followed_by_from_your_note(ask, question):
    first = ask(question)["text"].split("\n\n")[0]
    assert not (("your note" in first or "you noted" in first) and "From your" in first), first


def test_e17_the_real_route_reads_a_yearless_log_date_against_the_edit(ask, session):
    note = manager.create_entry(session, "# Trail log\n\nRan 9 km on 29 October.", category_name="Uncategorised")
    note.created_at = datetime(2026, 10, 14, 10)
    note.edited_at = datetime(2026, 11, 2, 10)
    session.commit()
    said = ask("when did I last run")["text"]
    assert "29 October 2026" in said or "2025" not in said, said
    assert "a year ago" not in said, said
