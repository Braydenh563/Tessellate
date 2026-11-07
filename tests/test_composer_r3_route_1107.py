"""Composer round 3, 2026-11-07 (audit-1107-composer-r3.md), through the chat
route (the pool the route builds is part of the answer). No model (fake
transport); fixed clock."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 11, 7, 10, 0, 0)
NOTES = (
    "# Dentist\n\nDr Patel at Kings Road practice. Phone 020 7946 0011. Next check-up Wednesday 11 November at 3pm.",
    "Dentist check-up on 11 November",
    "Number of the day: 7",
    "my number is in the safe",
    "# Passport\n\nExpires 12 March 2031. Number is in the safe.",
    "# Sara\n\nSara likes jazz.",
    "# Weekend plans\n\nSunday: call Mum and meet Sara for lunch at 1pm.",
    "# Uni timetable\n\nTuesday and Thursday are uni days. Cloud lab on Thursday afternoon.",
    "# Marathon\n\nRace is on 14 March in Brighton. Start is at 9am.",
)


@pytest.fixture
def go(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text in NOTES:
        entry = manager.create_entry(session, text, "Personal")
        entry.created_at = entry.updated_at = NOW - dt.timedelta(days=3)
    session.commit()
    return lambda q, chat=False: _ask(client, q, **({} if chat else {"notes_only": True, "answer_from": "notes"}))["text"]


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_r3_2_the_number_for_a_business_finds_the_note_that_holds_it(go, chat):
    said = go("what is the number for the dentist", chat)
    assert "020 7946 0011" in said and "no phone number" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_r3_2_a_person_with_no_number_is_denied_in_the_notebooks_name(go, chat):
    said = go("what is Sara's number", chat)
    assert said.startswith("None of your notes give a phone number for Sara."), said
    assert "likes jazz has no" not in said, said
