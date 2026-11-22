"""The filer's "looks like a duplicate of" pointer never outlives the note it names.

Source: LEDGER L-general-21 (docs/ARCHITECTURE.md:1806). `Entry.filing_similar_id` is not a
foreign key on purpose, and entry ids are handed to the next note made (no AUTOINCREMENT), so a
pointer left behind by a purge named an unrelated new note as the duplicate.
"""

from __future__ import annotations

from tessellate.core.database import Entry
from tessellate.entry import manager, manager_purge


def _two(session):
    kept = manager.create_entry(session, "the boiler manual, second copy", tags=[])
    gone = manager.create_entry(session, "the boiler manual", tags=[])
    kept.filing_similar_id = gone.id
    session.commit()
    return kept, gone


def test_purging_a_note_clears_every_pointer_to_it(session):
    kept, gone = _two(session)
    manager.soft_delete_entry(session, gone)
    session.commit()
    gone_id = gone.id
    manager_purge.purge_entries(session, [gone])
    session.expire_all()
    assert session.get(Entry, kept.id).filing_similar_id is None
    #: The id is free again: the next note may take it, and must not be named the duplicate.
    fresh = manager.create_entry(session, "a grocery list", tags=[])
    session.commit()
    assert fresh.id == gone_id
    assert session.get(Entry, kept.id).filing_similar_id is None


def test_the_launch_sweep_clears_pointers_left_dangling(session):
    kept, other = _two(session)
    session.execute(Entry.__table__.update().where(Entry.id == kept.id).values(filing_similar_id=9999))
    session.commit()
    assert manager_purge.clear_dangling_filing_similar(session) == 1
    session.expire_all()
    assert session.get(Entry, kept.id).filing_similar_id is None
    #: A pointer to a note that still exists stays.
    other.filing_similar_id = kept.id
    session.commit()
    assert manager_purge.clear_dangling_filing_similar(session) == 0
    session.expire_all()
    assert session.get(Entry, other.id).filing_similar_id == kept.id


def test_the_sweep_runs_with_the_bin_auto_clear(session, monkeypatch):
    from tessellate.api import app

    calls = []
    monkeypatch.setattr(manager_purge, "clear_dangling_filing_similar", lambda s: calls.append(s) or 0)
    app._purge_expired_bin_entries()
    assert len(calls) == 1
