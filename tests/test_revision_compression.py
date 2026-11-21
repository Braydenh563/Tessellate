"""Revision text is stored compressed (LEDGER L-world-class-696) and still searched and read."""

from __future__ import annotations

from sqlalchemy import text

from tessellate.ai import timetravel
from tessellate.core.database import Entry, EntryRevision

LONG = "The batch size was 32 and the learning rate was small. " * 40


def _raw(session, revision_id: int):
    return session.execute(text("SELECT content FROM entry_revisions WHERE id = :i"), {"i": revision_id}).scalar()


def test_a_long_revision_is_stored_smaller_and_reads_back_whole(session):
    entry = Entry(content="now")
    session.add(entry)
    session.flush()
    revision = EntryRevision(entry_id=entry.id, content=LONG)
    session.add(revision)
    session.commit()
    raw = _raw(session, revision.id)
    assert isinstance(raw, bytes) and len(raw) < len(LONG) // 4
    session.expire_all()
    assert session.get(EntryRevision, revision.id).content == LONG


def test_short_text_and_rows_written_before_stay_plain_and_read(session):
    entry = Entry(content="now")
    session.add(entry)
    session.flush()
    short = EntryRevision(entry_id=entry.id, content="first words")
    session.add(short)
    session.commit()
    assert _raw(session, short.id) == "first words"
    session.execute(
        text("INSERT INTO entry_revisions (id, entry_id, content, tags, created_at) VALUES (900, :e, :c, '[]', CURRENT_TIMESTAMP)"),
        {"e": entry.id, "c": LONG},
    )
    session.commit()
    assert _raw(session, 900) == LONG
    assert session.get(EntryRevision, 900).content == LONG


def test_time_travel_finds_a_past_word_in_compressed_revisions(session):
    entry = Entry(content="something else entirely")
    other = Entry(content="unrelated")
    session.add_all([entry, other])
    session.flush()
    session.add_all([EntryRevision(entry_id=entry.id, content=LONG), EntryRevision(entry_id=other.id, content="nothing here")])
    session.commit()
    found = timetravel.revision_candidates(session, "What was the Batch size?")
    assert [e.id for e in found] == [entry.id]
