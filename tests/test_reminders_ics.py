"""Reminders as an .ics calendar (WORLD_CLASS_PLAN §17 row 7, section 8 row 11).

"`.ics` export per reminder and for all": the one way a reminder reaches the
phone's calendar without a server in the middle. What must hold is what a
calendar app is strict about (RFC 5545): CRLF line ends, lines folded at 75
octets, text escaped, times in UTC with a `Z`, a stable UID so importing
twice updates rather than duplicates, and a repeat rule for a repeating
reminder. Plus two of this app's own rules: a private note's words never
leave in the file, and ticked-off reminders stay out unless asked for.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.core import vault
from tessellate.core.database import Reminder
import pytest
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)


def _due(days: int = 1) -> str:
    return (SUITE_NOW + timedelta(days=days)).replace(microsecond=0).isoformat()


def _add(client, text: str, **extra) -> dict:
    response = client.post("/reminders", json={"text": text, "due_at": _due(), **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _unfold(body: str) -> list[str]:
    """The logical lines, with RFC 5545 folding undone."""
    return body.replace("\r\n ", "").split("\r\n")


def test_one_reminder_is_a_valid_calendar(client):
    made = _add(client, "Call the vet, about Rex; bring the file\\notes")
    response = client.get(f"/reminders/{made['id']}/export.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "\n" not in body.replace("\r\n", "")  # no bare line feeds
    lines = _unfold(body)
    assert "VERSION:2.0" in lines and any(line.startswith("PRODID:") for line in lines)
    assert lines.count("BEGIN:VEVENT") == 1
    assert "SUMMARY:Call the vet\\, about Rex\\; bring the file\\\\notes" in lines
    start = next(line for line in lines if line.startswith("DTSTART:"))
    due = datetime.fromisoformat(made["due_at"]).astimezone(timezone.utc)
    assert start == "DTSTART:" + due.strftime("%Y%m%dT%H%M%SZ")
    assert f"UID:reminder-{made['id']}@memorymap.local" in lines
    assert "BEGIN:VALARM" in lines and "ACTION:DISPLAY" in lines


def test_a_title_cannot_write_its_own_lines_into_the_file(client):
    """A calendar file is lines, so a title carrying line ends is the
    injection to check (the review, 2026-09-26): "Buy milk\\r\\nEND:VEVENT..."
    must arrive as one SUMMARY with the breaks escaped, never as an event
    boundary of its own. Whatever the reminder API keeps of the breaks, the
    file has one event, and the escaper itself is held to the letter."""
    from tessellate.api.routes_reminders import _ics_text

    assert _ics_text("a\r\nb\nc\rd;e,f\\g") == "a\\nb\\nc\\nd\\;e\\,f\\\\g"
    made = _add(client, "Buy milk\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:forged")
    body = client.get(f"/reminders/{made['id']}/export.ics").text
    lines = _unfold(body)
    assert lines.count("BEGIN:VEVENT") == 1 and lines.count("END:VEVENT") == 1
    assert "SUMMARY:forged" not in lines
    assert sum(1 for line in lines if line.startswith("SUMMARY:")) == 1
    assert "\n" not in body.replace("\r\n", "") and "\r" not in body.replace("\r\n", "")


def test_every_line_is_folded_to_75_octets(client):
    made = _add(client, "é" * 200)  # two octets each: folding counts bytes, not characters
    body = client.get(f"/reminders/{made['id']}/export.ics").text
    for line in body.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, line
    summary = next(line for line in _unfold(body) if line.startswith("SUMMARY:"))
    assert summary == "SUMMARY:" + "é" * 200  # and nothing was split inside a character


def test_a_repeating_reminder_carries_its_rule(client):
    made = _add(client, "Water the plants", recurring="weekly")
    lines = _unfold(client.get(f"/reminders/{made['id']}/export.ics").text)
    assert "RRULE:FREQ=WEEKLY" in lines


def test_all_upcoming_by_default_and_done_ones_on_request(client):
    kept = _add(client, "Renew the passport", priority="high")
    done = _add(client, "Book the dentist")
    client.put(f"/reminders/{done['id']}", json={"done": True})
    lines = _unfold(client.get("/reminders/export.ics").text)
    assert lines.count("BEGIN:VEVENT") == 1
    assert f"UID:reminder-{kept['id']}@memorymap.local" in lines
    assert "PRIORITY:1" in lines
    both = _unfold(client.get("/reminders/export.ics?include_done=true").text)
    assert both.count("BEGIN:VEVENT") == 2
    assert "STATUS:COMPLETED" in both


def test_a_private_notes_words_do_not_leave_in_the_file(client, session):
    vault.create(session, "a passphrase")
    session.commit()
    note = client.post("/entries", json={"content": "The safe code is 4471"}).json()
    assert client.post(f"/entries/{note['id']}/privacy", json={"private": True}).status_code == 200
    made = _add(client, "Check the safe", entry_id=note["id"])
    body = client.get(f"/reminders/{made['id']}/export.ics").text
    assert "4471" not in body
    assert "SUMMARY:Check the safe" in _unfold(body)


def test_a_plain_notes_opening_is_the_description(client):
    note = client.post("/entries", json={"content": "Rex is due his booster in March"}).json()
    made = _add(client, "Vet", entry_id=note["id"])
    lines = _unfold(client.get(f"/reminders/{made['id']}/export.ics").text)
    assert "DESCRIPTION:Rex is due his booster in March" in lines


def test_an_empty_list_is_still_a_calendar(client):
    body = client.get("/reminders/export.ics").text
    assert body == "BEGIN:VCALENDAR\r\n" + body.split("BEGIN:VCALENDAR\r\n", 1)[1]
    assert "BEGIN:VEVENT" not in body and body.endswith("END:VCALENDAR\r\n")


def test_an_unknown_reminder_is_404(client):
    assert client.get("/reminders/999999/export.ics").status_code == 404


def test_the_uid_is_stable_across_exports(client, session):
    made = _add(client, "Stable")
    first = client.get(f"/reminders/{made['id']}/export.ics").text
    session.get(Reminder, made["id"]).text = "Stable, renamed"
    session.commit()
    second = client.get(f"/reminders/{made['id']}/export.ics").text
    uid = f"UID:reminder-{made['id']}@memorymap.local"
    assert uid in _unfold(first) and uid in _unfold(second)
