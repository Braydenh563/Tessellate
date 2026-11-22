"""Accepting a date makes a reminder; accepting a duplicate runs Tidy's merge (L-world-class-27).
Fixed clock, no model: the night pass reads both by rule."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from tessellate.core.database import DerivedFact, Entry, Reminder
from tests._clock import pin_clock
from tests._frozen_clock import FIXED_NOW

NOTE = "Sign the lease at the studio on 12 March 2027."


def _note(client, content: str) -> int:
    return client.post("/entries", json={"content": content}).json()["id"]


def _night(client) -> None:
    client.post("/night/run", json={"budget": 4000, "force": True})


def _fact(session, kind: str) -> DerivedFact:
    return session.scalars(select(DerivedFact).where(DerivedFact.kind == kind)).first()


def _freeze(monkeypatch, now: datetime = FIXED_NOW) -> None:
    pin_clock(monkeypatch, now)


def test_accepting_a_date_makes_a_reminder_on_that_day_at_nine(ai_client, fake_ollama, session, monkeypatch):
    note = _note(ai_client, NOTE)
    _night(ai_client)
    _freeze(monkeypatch)
    fact = _fact(session, "date")
    done = ai_client.post(f"/learned/{fact.id}/accept")
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["kind"] == "reminder" and body["due_at"] == "2027-03-12T09:00:00+00:00" and not body["existing"]
    reminder = session.get(Reminder, body["reminder_id"])
    assert (reminder.entry_id, reminder.text, reminder.due_at) == (note, NOTE, datetime(2027, 3, 12, 9, tzinfo=timezone.utc))
    reply = ai_client.get(f"/learned/{fact.id}")
    assert reply.status_code == 404, "an accepted fact leaves the list"


def test_accepting_a_date_again_after_restore_makes_no_second_reminder(ai_client, fake_ollama, session, monkeypatch):
    _note(ai_client, NOTE)
    _night(ai_client)
    _freeze(monkeypatch)
    fact_id = _fact(session, "date").id
    first = ai_client.post(f"/learned/{fact_id}/accept").json()
    ai_client.post(f"/learned/{fact_id}/restore")
    second = ai_client.post(f"/learned/{fact_id}/accept").json()
    assert second["existing"] and second["reminder_id"] == first["reminder_id"]
    assert len(session.scalars(select(Reminder)).all()) == 1


def test_a_date_that_has_passed_is_refused_and_the_fact_stays(ai_client, fake_ollama, session, monkeypatch):
    _note(ai_client, NOTE)
    _night(ai_client)
    _freeze(monkeypatch, datetime(2027, 6, 1, tzinfo=timezone.utc))
    fact = _fact(session, "date")
    done = ai_client.post(f"/learned/{fact.id}/accept")
    assert done.status_code == 422 and "passed" in done.json()["detail"]
    reply = ai_client.get(f"/learned/{fact.id}")
    assert reply.status_code == 200
    assert session.scalars(select(Reminder)).first() is None


def test_accepting_a_duplicate_bins_the_later_note_and_the_undo_brings_it_back(ai_client, fake_ollama, session, monkeypatch):
    first = _note(ai_client, NOTE)
    second = _note(ai_client, NOTE)
    _night(ai_client)
    _freeze(monkeypatch)
    fact = _fact(session, "duplicate")
    done = ai_client.post(f"/learned/{fact.id}/accept")
    assert done.status_code == 200, done.text
    body = done.json()
    assert (body["kind"], body["keeper"], body["binned"]) == ("merge", first, [second])
    session.expire_all()
    assert session.get(Entry, second).is_deleted and not session.get(Entry, first).is_deleted
    assert session.get(Entry, first).content == NOTE, "identical notes merge to one copy, not two"
    reply = ai_client.post(f"/tidy/undo/{body['undo_id']}")
    assert reply.status_code == 200
    session.expire_all()
    assert not session.get(Entry, second).is_deleted


def test_a_duplicate_whose_original_is_gone_is_refused(ai_client, fake_ollama, session, monkeypatch):
    first = _note(ai_client, NOTE)
    _note(ai_client, NOTE)
    _night(ai_client)
    _freeze(monkeypatch)
    ai_client.delete(f"/entries/{first}")
    fact = _fact(session, "duplicate")
    reply = ai_client.post(f"/learned/{fact.id}/accept")
    assert reply.status_code == 422


def test_an_entity_or_a_claim_cannot_be_accepted(ai_client, fake_ollama, session):
    _note(ai_client, NOTE)
    _night(ai_client)
    other = session.scalars(select(DerivedFact).where(DerivedFact.kind.not_in(("date", "duplicate")))).first()
    if other is not None:
        reply = ai_client.post(f"/learned/{other.id}/accept")
        assert reply.status_code == 422


def test_the_morning_card_wires_both_accepts_and_help_names_them():
    from tests._app_js import app_js_text
    from tests._help_text import help_more_text

    js = app_js_text()
    assert "/learned/${fact.id}/accept" in js and "NIGHT_ACCEPT" in js
    assert "ph:bell" in js and "ph:arrows-merge" in js
    assert "merge a repeated note" in help_more_text()
