"""INBOX 1525, side finding: what `defer_filing` leaves in the job queue.

`defer_filing` does not stop the filing job, it is what makes one: the note is
saved as 'pending' and a `file-entry` job settles it (5,000 seeded notes left
5,000 jobs). Two things do stop it, because a model has nothing to decide:
a category the caller names, and a parent note. A seed that wants no jobs
names a category.
"""

from __future__ import annotations

import pytest

from tessellate.api import routes_entries


@pytest.fixture
def queued(monkeypatch):
    ids: list[int] = []
    monkeypatch.setattr(routes_entries, "_queue_filing", lambda entry: ids.append(entry.id))
    return ids


def test_defer_filing_alone_queues_one_job_a_note(client, queued):
    made = [client.post("/entries", json={"content": f"seed note {i}", "defer_filing": True}).json() for i in range(3)]
    assert queued == [m["id"] for m in made]
    assert {m["filing_state"] for m in made} == {"pending"}


def test_a_named_category_stops_the_job(client, queued):
    made = client.post("/entries", json={"content": "seed note", "defer_filing": True, "category": "Work"}).json()
    assert queued == []
    assert made["filing_state"] != "pending"


def test_a_parent_note_stops_the_job(client, queued):
    parent = client.post("/entries", json={"content": "the thread", "category": "Work"}).json()
    made = client.post("/entries", json={"content": "a reply", "defer_filing": True, "parent_id": parent["id"]}).json()
    assert queued == []
    assert made["filing_state"] != "pending"
