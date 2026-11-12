"""Audit 1028 K32: the page's minute look is a stamp, and the list is fetched only when it moved."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")


def _make(client, text, due="2099-01-01T09:00:00"):
    return client.post("/reminders", json={"text": text, "due_at": due}).json()


def test_an_empty_notebook_answers_nothing_open(client):
    body = client.get("/reminders/due").json()
    assert (body["open"], body["next_due_at"]) == (0, None)


def test_the_stamp_moves_when_the_open_list_does_and_not_otherwise(client):
    first = _make(client, "water the plants")
    one = client.get("/reminders/due").json()
    assert client.get("/reminders/due").json() == one, "asking twice changes nothing"
    assert one["open"] == 1 and one["next_due_at"].startswith("2099-01-01")

    _make(client, "call the dentist", "2098-06-01T09:00:00")
    two = client.get("/reminders/due").json()
    assert two["open"] == 2 and two["stamp"] != one["stamp"]
    assert two["next_due_at"].startswith("2098-06-01"), "the soonest one leads"

    client.put(f"/reminders/{first['id']}", json={"text": "water the ferns"})
    three = client.get("/reminders/due").json()
    assert three["stamp"] != two["stamp"], "a reworded reminder is a changed list"

    client.post(f"/reminders/{first['id']}/complete")
    four = client.get("/reminders/due").json()
    assert four["open"] == 1 and four["stamp"] != three["stamp"], "ticking one off removes it"


def test_the_look_is_small(client):
    for n in range(30):
        _make(client, f"item {n}", f"2099-01-{n % 28 + 1:02d}T09:00:00")
    assert len(client.get("/reminders/due").content) < 200


def test_the_page_fetches_the_list_only_when_the_stamp_moved():
    body = STATUS.split("const openReminderList = (() => {", 1)[1].split("\n})();\n", 1)[0]
    assert body.index('"/reminders/due"') < body.index('"/reminders?include_done=false')
    assert "look.stamp === cache.stamp" in body
    assert "fetched: false" in body and "fetched: true" in body
    poll = STATUS.split("async function checkDueReminders() {", 1)[1].split("\n}\n", 1)[0]
    assert "openReminderList()" in poll and 'apiJson("/reminders?include_done=false"' not in poll
    assert "if (looked.fetched) reminderChannel?.postMessage(all)" in poll


def test_the_list_can_be_limited_to_a_due_window(client, monkeypatch):
    from datetime import datetime, timezone

    from tessellate.api import routes_reminders

    #: A fixed clock (CLAUDE.md section 8): the window counts from this minute.
    monkeypatch.setattr(routes_reminders, "utcnow", lambda: datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc))
    _make(client, "soon", "2026-11-14T09:00:00Z")
    _make(client, "past the window", "2026-12-20T09:00:00Z")
    everything = client.get("/reminders?include_done=false").json()
    windowed = client.get("/reminders?include_done=false&due_within_days=31")
    assert len(everything) == 2
    assert [r["text"] for r in windowed.json()] == ["soon"], "31 days from 12 November ends 13 December"
    assert windowed.headers["X-Total-Count"] == "1", "the total counts the same window"


def test_the_minute_poll_asks_for_the_window_and_keeps_the_open_count():
    body = STATUS.split("const openReminderList = (() => {", 1)[1].split("\n})();\n", 1)[0]
    assert "include_done=false&due_within_days=" in body
    assert "open: look?.open" in body
