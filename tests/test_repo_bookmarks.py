"""The bookmarks repository's verbs, against a real session (INBOX 1499).

The route tests (`test_bookmarks_api.py`, `test_entry_bookmarks.py`,
`test_document_bookmarks.py`) hold the HTTP behaviour unchanged; these hold
the repository's own contract: it flushes but leaves the commit to its caller,
and its errors are the domain names the routes answer with.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.core.database import Document, Entry, EntryBookmark
from tessellate.repo import Invalid, NotFound, bookmarks


def test_create_cleans_fields_and_names_an_earlier_twin(session):
    first, twin = bookmarks.create(session, url=" example.com ", title=" Ex ", note="", group_name="")
    assert (first.url, first.title, twin) == ("https://example.com", "Ex", None)
    second, twin = bookmarks.create(session, url="https://example.com", title="", note="", group_name="")
    assert twin == first.id and second.id != first.id


def test_a_disallowed_scheme_is_invalid_not_stored(session):
    with pytest.raises(Invalid) as raised:
        bookmarks.create(session, url="javascript:alert(1)", title="", note="", group_name="")
    assert raised.value.status_code == 422
    assert bookmarks.page(session, limit=10, offset=0) == ([], 0)


def test_page_puts_pinned_first_then_newest_and_counts_all(session):
    old, _ = bookmarks.create(session, url="a.test", title="", note="", group_name="")
    old.created_at = datetime(2026, 1, 1)
    new, _ = bookmarks.create(session, url="b.test", title="", note="", group_name="")
    new.created_at = datetime(2026, 2, 1)
    pinned, _ = bookmarks.create(session, url="c.test", title="", note="", group_name="", pinned=True)
    pinned.created_at = datetime(2025, 1, 1)
    session.flush()
    rows, total = bookmarks.page(session, limit=2, offset=0)
    assert [r.id for r in rows] == [pinned.id, new.id] and total == 3


def test_update_leaves_none_fields_alone_and_misses_are_not_found(session):
    mark, _ = bookmarks.create(session, url="a.test", title="Keep", note="n", group_name="")
    bookmarks.update(session, mark.id, url=None, title=None, note=" new ", pinned=True)
    assert (mark.title, mark.note, mark.pinned) == ("Keep", "new", True)
    with pytest.raises(NotFound):
        bookmarks.update(session, mark.id + 99, title="x")


def test_attach_is_once_and_detach_answers_when_it_was_attached(session):
    entry = Entry(content="A note")
    session.add(entry)
    session.flush()
    mark, _ = bookmarks.create(session, url="a.test", title="", note="", group_name="")
    when = datetime(2026, 3, 4, 5, 6)
    assert bookmarks.attach_to_entry(session, entry.id, mark.id, created_at=when)
    assert not bookmarks.attach_to_entry(session, entry.id, mark.id)
    assert [b.id for b in bookmarks.attached_to_entry(session, entry.id)] == [mark.id]
    assert bookmarks.detach_from_entry(session, entry.id, mark.id).replace(tzinfo=None) == when
    assert bookmarks.detach_from_entry(session, entry.id, mark.id) is None
    assert bookmarks.attached_to_entry(session, entry.id) == []


def test_delete_takes_the_join_rows_with_it(session):
    entry = Entry(content="A note")
    document = Document(title="Doc", content="")
    session.add_all([entry, document])
    session.flush()
    mark, _ = bookmarks.create(session, url="a.test", title="", note="", group_name="")
    bookmarks.attach_to_entry(session, entry.id, mark.id)
    bookmarks.attach_to_document(session, document.id, mark.id)
    bookmarks.delete(session, mark.id)
    assert bookmarks.find(session, mark.id) is None
    assert session.query(EntryBookmark).count() == 0
    assert bookmarks.attached_to_document(session, document.id) == []


def test_a_repository_verb_leaves_the_commit_to_its_caller(session):
    mark, _ = bookmarks.create(session, url="a.test", title="", note="", group_name="")
    session.rollback()
    assert bookmarks.find(session, mark.id) is None

