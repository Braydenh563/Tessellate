"""The capture service, called directly (decision 55, L-world-class-632): a
save runs without a request, and a resend of the same save is answered with
the first note instead of a second one."""

from __future__ import annotations

from tessellate.api.schemas import EntryCreate
from tessellate.entry import capture, manager


def _body(**fields) -> EntryCreate:
    return EntryCreate(content="# Bread\nflour and water", category="Cooking", **fields)


def test_a_save_keeps_the_chosen_category_and_starts_nothing_until_asked(session, monkeypatch):
    queued: list[int] = []
    monkeypatch.setattr(capture.filing_background, "_queue_filing", lambda entry: queued.append(entry.id))
    made = capture.create(session, _body())
    assert made.fresh and made.filed_by == "user" and not made.defer
    assert manager.category_name_for(session, made.entry) == "Cooking"
    assert queued == []
    capture.start_background(made)
    assert queued == []  # filed already: nothing to queue


def test_a_resend_with_the_same_key_returns_the_first_note(session):
    first = capture.create(session, _body(client_key="abc-123"))
    capture.start_background(first)
    again = capture.create(session, _body(client_key="abc-123"))
    assert again.entry.id == first.entry.id
    assert not again.fresh and again.similar is None


def test_a_deferred_save_is_pending_and_queued_by_start_background(session, monkeypatch):
    queued: list[int] = []
    monkeypatch.setattr(capture.filing_background, "_queue_filing", lambda entry: queued.append(entry.id))
    body = EntryCreate(content="a thought to file later", defer_filing=True)
    made = capture.create(session, body)
    assert made.defer and made.entry.filing_state == "pending"
    capture.start_background(made)
    assert queued == [made.entry.id]
