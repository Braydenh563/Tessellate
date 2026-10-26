"""Add to Google Calendar and Add to Outlook (the owner, 2026-10-27: "Alerts +
Google/Outlook buttons").

The server only builds two addresses; the browser opens one on a click, so
nothing leaves this computer until the person presses it. The rules are the
.ics file's: the reminder's own words, a plain note's opening as the details,
and a private note's words never. Every exported event also carries an alert,
at the due time unless the reminder has its own lead.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from tessellate.core import vault


def _due(days: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()


def _add(client, text: str, **extra) -> dict:
    response = client.post("/reminders", json={"text": text, "due_at": _due(), **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _stamp(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def test_every_event_has_an_alert_at_the_due_time(client):
    made = _add(client, "Ring the dentist")
    body = client.get(f"/reminders/{made['id']}/export.ics").text
    assert "BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:Ring the dentist\r\nTRIGGER:PT0M\r\nEND:VALARM\r\n" in body


def test_a_reminders_own_lead_is_the_alert(client):
    made = _add(client, "Train", alert_minutes=90)
    body = client.get(f"/reminders/{made['id']}/export.ics").text
    assert "TRIGGER:-PT90M" in body


def test_google_link_is_prefilled(client):
    made = _add(client, "Call Mum, about Sunday", recurring="weekly")
    links = client.get(f"/reminders/{made['id']}/calendar-links").json()
    parts = urlsplit(links["google"])
    assert (parts.scheme, parts.netloc, parts.path) == ("https", "calendar.google.com", "/calendar/render")
    query = parse_qs(parts.query)
    assert query["action"] == ["TEMPLATE"]
    assert query["text"] == ["Call Mum, about Sunday"]
    start = _stamp(made["due_at"])
    end = (datetime.strptime(start, "%Y%m%dT%H%M%SZ") + timedelta(minutes=15)).strftime("%Y%m%dT%H%M%SZ")
    assert query["dates"] == [f"{start}/{end}"]
    assert query["recur"] == ["RRULE:FREQ=WEEKLY"]


def test_outlook_link_is_prefilled(client):
    made = _add(client, "Pay the invoice")
    links = client.get(f"/reminders/{made['id']}/calendar-links").json()
    parts = urlsplit(links["outlook"])
    assert (parts.scheme, parts.netloc) == ("https", "outlook.live.com")
    assert parts.path == "/calendar/0/deeplink/compose"
    query = parse_qs(parts.query)
    assert query["subject"] == ["Pay the invoice"]
    start = datetime.fromisoformat(made["due_at"]).astimezone(timezone.utc)
    assert query["startdt"] == [start.strftime("%Y-%m-%dT%H:%M:%SZ")]
    assert query["enddt"] == [(start + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")]


def test_a_plain_notes_opening_is_the_details(client):
    note = client.post("/entries", json={"content": "Rex is due his booster in March"}).json()
    made = _add(client, "Vet", entry_id=note["id"])
    links = client.get(f"/reminders/{made['id']}/calendar-links").json()
    assert parse_qs(urlsplit(links["google"]).query)["details"] == ["Rex is due his booster in March"]
    assert parse_qs(urlsplit(links["outlook"]).query)["body"] == ["Rex is due his booster in March"]


def test_a_private_notes_words_never_go_in_a_link(client, session):
    vault.create(session, "a passphrase")
    session.commit()
    note = client.post("/entries", json={"content": "The safe code is 4471"}).json()
    private = client.post(f"/entries/{note['id']}/privacy", json={"private": True})
    assert private.status_code == 200
    made = _add(client, "Check the safe", entry_id=note["id"])
    links = client.get(f"/reminders/{made['id']}/calendar-links").json()
    for url in links.values():
        assert "4471" not in url and "details" not in url and "body" not in url


def test_an_unknown_reminder_is_404(client):
    assert client.get("/reminders/999999/calendar-links").status_code == 404


def test_the_menu_and_the_chat_use_them():
    """The wiring a server test cannot see: the reminder menu opens the provider
    page on the press, the chat offers after the turn is saved, and the selection
    menu hands its note to the reminder."""
    from tests._app_js import app_js_text

    js = app_js_text()
    assert "Add to Google Calendar" in js and "Add to Outlook" in js
    assert "/calendar-links" in js and "tab.opener = null" in js
    assert "offerReminder(bubble, question);" in js and "\"/reminders/suggest\"" in js
    assert "remindFromSelection(text, noteId)" in js and "entry_id: entryId" in js
