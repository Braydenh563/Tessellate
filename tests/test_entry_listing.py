"""The listing service, called directly (decision 55, L-world-class-632)."""

from __future__ import annotations

import pytest

from tessellate.entry import listing, manager


def _note(session, text: str):
    entry = manager.create_entry(session, text, category_name=manager.UNCATEGORISED)
    session.commit()
    return entry


def test_a_page_says_where_the_next_one_starts(session):
    for n in range(3):
        _note(session, f"note {n}")
    first = listing.notes_page(session, limit=2, offset=0, boards=manager.BOARDS_EXCLUDE, after=None)
    assert len(first.entries) == 2 and first.total == 3 and first.next_key is not None
    last = listing.notes_page(session, limit=5, offset=0, boards=manager.BOARDS_EXCLUDE, after=None)
    assert len(last.entries) == 3 and last.next_key is None


def test_the_bin_lists_only_what_was_deleted(session):
    kept, binned = _note(session, "kept"), _note(session, "binned")
    manager.soft_delete_entry(session, binned)
    session.commit()
    entries, total = listing.bin_page(session, deleted=True, limit=10, offset=0)
    assert [e.id for e in entries] == [binned.id] and total == 1
    assert kept.id not in [e.id for e in entries]


def test_a_since_this_app_did_not_write_is_refused(session):
    with pytest.raises(ValueError, match="not one this app wrote"):
        listing.changes(session, "last tuesday")
    assert listing.changes(session, "")["ids"] == []


def test_a_query_with_no_terms_answers_empty(session):
    assert listing.query(session, "")["ids"] == []
