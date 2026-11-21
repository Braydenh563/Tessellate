"""The date and time pickers read a typed phrase with `ai/when` (UI_MODERNISATION_PLAN
Phase 12 decision 5): `POST /reminders/when` answers wall-clock parts on the
person's clock, makes nothing, and says 422 for words that are not a time."""

from __future__ import annotations

from datetime import timedelta, timezone

from tessellate.core.database import utcnow
import pytest
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)


def test_a_typed_phrase_comes_back_as_a_date_and_a_time_on_the_persons_clock(client):
    offset = 600  # ten hours east, where "tomorrow" is not the server's
    local = utcnow().astimezone(timezone(timedelta(minutes=offset)))
    got = client.post("/reminders/when", json={"text": "tomorrow at 3pm", "tz_offset_minutes": offset})
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["date"] == (local + timedelta(days=1)).strftime("%Y-%m-%d")
    assert body["time"] == "15:00"
    iso = client.post("/reminders/when", json={"text": "2031-04-05 09:30", "tz_offset_minutes": 0}).json()
    assert (iso["date"], iso["time"]) == ("2031-04-05", "09:30")
    listed = client.get("/reminders").json()
    assert listed == [], "reading a time must not make a reminder"


def test_words_that_are_not_a_time_are_a_422_with_a_sentence(client):
    got = client.post("/reminders/when", json={"text": "purple elephant", "tz_offset_minutes": 0})
    assert got.status_code == 422
    assert "date or time" in got.json()["detail"]
    empty = client.post("/reminders/when", json={"text": ""})
    assert empty.status_code == 422
