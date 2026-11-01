"""The branches of `tensions.derive` that the table tests leave unpinned.

Characterisation tests written before the function was split by source
(cc-1101): a malformed event or fact is skipped rather than raised, a reopened
pair is open again, a tombstoned night fact is a dismissal, a fact about its
own note is no pair, and two notes with the same timestamp order by id.
"""

from __future__ import annotations

import json
from datetime import timedelta

from tessellate.ai import tensions
from tessellate.core import events
from tessellate.core.database import DerivedFact, Entry, utcnow

NOW = utcnow()


def _note(session, text, days_ago=0, *, same_instant=False):  # noqa: ANN001, ANN201
    entry = Entry(content=text, tags=json.dumps([]))
    entry.created_at = NOW if same_instant else NOW - timedelta(days=days_ago)
    session.add(entry)
    session.commit()
    return entry


def _fact(session, entry, payload, *, deleted=False):  # noqa: ANN001, ANN201
    row = DerivedFact(
        entry_id=entry.id,
        kind="tension",
        text="x",
        span_start=0,
        span_end=1,
        model="local",
        confidence=0.5,
        computed_at=NOW,
        payload=payload,
    )
    if deleted:
        row.deleted_at = NOW
    session.add(row)
    session.commit()
    return row


def _statuses(session):  # noqa: ANN001, ANN201
    return {row["pair"]: row["status"] for row in tensions.derive(session)}


def test_an_event_without_both_ids_is_skipped(session):
    events.record(session, tensions.FOUND, tensions.EVENT_TYPE, 1, payload={"earlier_id": "x"})
    events.record(session, tensions.FOUND, tensions.EVENT_TYPE, 1, payload=None)
    session.commit()
    assert tensions.derive(session) == []


def test_a_reopened_pair_is_open_again_whether_dismissed_or_accepted(session):
    a, b, c, d = (_note(session, t, n) for t, n in (("A", 9), ("B", 8), ("C", 7), ("D", 6)))
    for first, second in ((a, b), (c, d)):
        tensions.record_event(session, tensions.FOUND, first.id, second.id, reason="r", model="m", confidence=0.7)
    tensions.record_event(session, tensions.DISMISSED, a.id, b.id)
    tensions.record_event(session, tensions.ACCEPTED, c.id, d.id)
    session.commit()
    assert _statuses(session) == {f"{a.id}:{b.id}": "dismissed", f"{c.id}:{d.id}": "dismissed"}
    tensions.record_event(session, tensions.REOPENED, a.id, b.id)
    tensions.record_event(session, tensions.REOPENED, c.id, d.id)
    session.commit()
    assert _statuses(session) == {f"{a.id}:{b.id}": "open", f"{c.id}:{d.id}": "open"}


def test_a_night_fact_with_a_bad_payload_or_about_its_own_note_is_skipped(session):
    a, b = _note(session, "A", 9), _note(session, "B", 8)
    _fact(session, a, "not json")
    _fact(session, a, json.dumps({"reason": "no other note named"}))
    _fact(session, a, json.dumps({"other_entry_id": a.id, "reason": "itself"}))
    _fact(session, a, json.dumps({"other_entry_id": b.id, "reason": "real"}))
    rows = tensions.derive(session)
    assert [(r["pair"], r["reason"], r["source"], r["status"]) for r in rows] == [
        (f"{a.id}:{b.id}", "real", "night", "open")
    ]


def test_a_tombstoned_night_fact_is_a_dismissed_pair(session):
    a, b = _note(session, "A", 9), _note(session, "B", 8)
    _fact(session, b, json.dumps({"other_entry_id": a.id, "reason": "gone"}), deleted=True)
    (row,) = tensions.derive(session)
    assert (row["status"], row["source"], row["earlier_id"], row["later_id"]) == ("dismissed", "night", a.id, b.id)


def test_notes_written_at_the_same_instant_order_by_id(session):
    first = _note(session, "A", same_instant=True)
    second = _note(session, "B", same_instant=True)
    _fact(session, first, json.dumps({"other_entry_id": second.id, "reason": "tie"}))
    (row,) = tensions.derive(session)
    assert (row["earlier_id"], row["later_id"]) == (first.id, second.id)
