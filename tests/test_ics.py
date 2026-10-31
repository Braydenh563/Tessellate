"""ICS both ways for reminders (TIMELINE_PLAN section 9, decision 17, step 4).

The gate: a round trip of 20 reminders is equal, and an import with a bad
line reports it and keeps the rest. Plus what a calendar from elsewhere
sends: a floating time read on the reader's clock, a date with no time, a
zone by name, a repeat, an alarm and a completed status.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.core import ics_import

FIELDS = ("text", "due_at", "priority", "recurring", "alert_minutes", "done")
REPEATS = ("none", "daily", "weekly", "monthly", "FREQ=WEEKLY;INTERVAL=2")


def _upload(client, body: str, tz: int = 0):
    return client.post(
        "/reminders/import.ics",
        files={"file": ("cal.ics", body.encode("utf-8"), "text/calendar")},
        data={"tz_offset_minutes": str(tz)},
    )


def _make_twenty(client) -> list[dict]:
    base = datetime.now(timezone.utc).replace(microsecond=0, second=0) + timedelta(days=2)
    made = []
    for i in range(20):
        body = {
            "text": f"Reminder {i}, with a comma; and a semicolon" if i % 3 == 0 else f"Reminder {i}",
            "due_at": (base + timedelta(hours=7 * i)).isoformat(),
            "priority": ("low", "normal", "high")[i % 3],
            "recurring": REPEATS[i % len(REPEATS)],
        }
        if i % 4 == 0:
            body["alert_minutes"] = 15 * (i + 1)
        response = client.post("/reminders", json=body)
        assert response.status_code == 201, response.text
        made.append(response.json())
    return made


def _rows(client) -> list[tuple]:
    rows = client.get("/reminders?limit=1000").json()
    return sorted(tuple(row[key] for key in FIELDS) for row in rows)


def test_a_round_trip_of_twenty_reminders_is_equal(client):
    _make_twenty(client)
    before = _rows(client)
    exported = client.get("/reminders/export.ics?include_done=true").text
    for row in client.get("/reminders?limit=1000").json():
        gone = client.delete(f"/reminders/{row['id']}")
        assert gone.status_code == 200
    left = client.get("/reminders?limit=1000").json()
    assert left == []
    report = _upload(client, exported).json()
    assert len(report["added"]) == 20 and report["updated"] == [] and report["skipped"] == []
    assert _rows(client) == before


def test_importing_its_own_export_twice_updates_rather_than_doubles(client):
    _make_twenty(client)
    exported = client.get("/reminders/export.ics").text
    report = _upload(client, exported).json()
    assert report["added"] == [] and len(report["updated"]) == 20
    assert len(client.get("/reminders?limit=1000").json()) == 20


def test_a_bad_line_is_reported_and_the_rest_kept(client):
    ahead = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y%m%dT%H%M%SZ")
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "BEGIN:VEVENT", "SUMMARY:Good one", f"DTSTART:{ahead}", "END:VEVENT",
        "BEGIN:VEVENT", "SUMMARY:Broken start", "DTSTART:next tuesday-ish", "END:VEVENT",
        "BEGIN:VEVENT", f"DTSTART:{ahead}", "END:VEVENT",
        "BEGIN:VEVENT", "SUMMARY:Another good one", f"DTSTART:{ahead}", "END:VEVENT",
        "END:VCALENDAR", "",
    ])
    response = _upload(client, body)
    assert response.status_code == 200, response.text
    report = response.json()
    assert len(report["added"]) == 2
    reasons = [row["reason"] for row in report["skipped"]]
    assert len(reasons) == 2
    assert reasons[0].startswith("line 9:") and "not a date" in reasons[0]
    assert "no summary" in reasons[1]
    texts = sorted(row["text"] for row in client.get("/reminders").json())
    assert texts == ["Another good one", "Good one"]


def test_a_file_that_is_not_a_calendar_is_refused(client):
    assert _upload(client, "hello").status_code == 422


def test_a_past_one_off_is_skipped_but_a_completed_one_kept(client):
    body = "\r\n".join([
        "BEGIN:VCALENDAR",
        "BEGIN:VEVENT", "SUMMARY:Long gone", "DTSTART:20200101T090000Z", "END:VEVENT",
        "BEGIN:VEVENT", "SUMMARY:Done long ago", "DTSTART:20200101T090000Z", "STATUS:COMPLETED", "END:VEVENT",
        "END:VCALENDAR",
    ])
    report = _upload(client, body).json()
    assert len(report["added"]) == 1
    assert "already past" in report["skipped"][0]["reason"]


def test_what_another_calendar_sends_is_read():
    reading = ics_import.read(
        "\r\n".join([
            "BEGIN:VCALENDAR",
            "BEGIN:VEVENT", "SUMMARY:Floating", "DTSTART:20301005T140000", "PRIORITY:2",
            "BEGIN:VALARM", "TRIGGER:-PT1H30M", "END:VALARM", "END:VEVENT",
            "BEGIN:VEVENT", "SUMMARY:All day", "DTSTART;VALUE=DATE:20301006", "RRULE:FREQ=WEEKLY", "END:VEVENT",
            "BEGIN:VEVENT", "SUMMARY:Zoned", "DTSTART;TZID=Europe/Paris:20300706T100000",
            "BEGIN:VALARM", "TRIGGER:-P1D", "END:VALARM", "STATUS:COMPLETED", "END:VEVENT",
            "BEGIN:VEVENT", "SUMMARY:Folded summary that goes on",
            " and on", "DTSTART:20301007T080000Z", "PRIORITY:9", "END:VEVENT",
            "END:VCALENDAR",
        ]),
        tz_offset_minutes=120,
    )
    assert not reading.skipped
    floating, all_day, zoned, folded = reading.events
    assert floating.due_at == datetime(2030, 10, 5, 12, 0) and floating.priority == "high"
    assert floating.alert_minutes == 90
    assert all_day.due_at == datetime(2030, 10, 6, 7, 0) and all_day.recurring == "weekly"
    assert zoned.due_at == datetime(2030, 7, 6, 8, 0) and zoned.done and zoned.alert_minutes == 1440
    assert folded.text == "Folded summary that goes onand on" and folded.priority == "low"


def test_the_import_runs_off_the_event_loop():
    """Audit 1028 K17: a per-event query loop inside `async def` froze the server."""
    import inspect

    from tessellate.api import routes_reminders

    assert not inspect.iscoroutinefunction(routes_reminders.import_ics)
