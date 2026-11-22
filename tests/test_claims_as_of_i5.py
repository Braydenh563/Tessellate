"""WORLD_CLASS_PLAN I5: `GET /entries/{id}/claims?as_of=`.

A note's claims as they stood on a day, each traced to the revision its text
came from. Claims are not stored per revision (the plan's "claims carry
`revision_id`" was never so); the revision is resolved at the date, the way
then-and-now does, and a claim the night shift stored for the note now is
named by its fact id. A sentence the person marked wrong (I7) says so.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.ai import verdicts
from tessellate.core.database import DerivedFact, EntryRevision
from tessellate.entry import manager

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
THEN = "The batch size should stay at 32. We train on the March dataset only."
NOW = "The batch size is 64 after the memory fix. We train on the March dataset only."


def _note(session):
    entry = manager.create_entry(session, NOW, "Work", [])
    entry.created_at = T0
    revision = EntryRevision(entry_id=entry.id, content=THEN, tags="[]", created_at=T0 + timedelta(days=30))
    session.add(revision)
    session.commit()
    return entry, revision


def _day(days: int) -> str:
    return (T0 + timedelta(days=days)).date().isoformat()


def test_the_claims_as_of_a_day_are_that_revisions_claims(ai_client, session):
    entry, revision = _note(session)
    body = ai_client.get(f"/entries/{entry.id}/claims", params={"as_of": _day(10)}).json()
    assert body["revision_id"] == revision.id and body["exact"] is True
    assert [c["text"] for c in body["claims"]] == [
        "The batch size should stay at 32.", "We train on the March dataset only.",
    ]


def test_without_a_day_the_claims_are_now_and_name_stored_facts_and_verdicts(ai_client, session):
    entry, _ = _note(session)
    fact = DerivedFact(entry_id=entry.id, kind="claim", text="We train on the March dataset only.", model="fake", confidence=0.8)
    session.add(fact)
    session.commit()
    start = NOW.index("The batch")
    verdicts.mark(session, verdicts.WRONG, entry.id, "The batch size is 64 after the memory fix.", start, start + 42)
    session.commit()
    body = ai_client.get(f"/entries/{entry.id}/claims").json()
    assert body["revision_id"] is None and body["as_of"] is None
    rows = {c["text"]: c for c in body["claims"]}
    assert rows["We train on the March dataset only."]["fact_id"] == fact.id
    assert rows["The batch size is 64 after the memory fix."]["wrong"] is True
    assert rows["We train on the March dataset only."]["wrong"] is False


def test_before_the_note_existed_is_a_404_and_a_private_note_a_403(ai_client, session):
    entry, _ = _note(session)
    assert ai_client.get(f"/entries/{entry.id}/claims", params={"as_of": "2025-01-01"}).status_code == 404
    entry.is_private = True
    session.commit()
    assert ai_client.get(f"/entries/{entry.id}/claims").status_code == 403
