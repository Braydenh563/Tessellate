"""The note-links repository's verbs, against a real session (INBOX 1499).

The link routes' own tests hold the routes unchanged; these hold the
repository's reads: the stored pairs, a note's neighbours, a link only if it
is on the note, the untyped scan, the wiki sources, the counts.
"""

from __future__ import annotations

import pytest

from tessellate.core.database import Entry, EntryLink
from tessellate.repo import NotFound, relations


def _notes(session, n: int) -> list[Entry]:
    rows = [Entry(content=f"n{i}") for i in range(n)]
    session.add_all(rows)
    session.flush()
    return rows


def _link(session, a: Entry, b: Entry, **kw) -> EntryLink:
    row = EntryLink(source_entry_id=a.id, target_entry_id=b.id, **kw)
    session.add(row)
    session.flush()
    return row


def test_find_and_get_for_note_only_answer_a_link_on_that_note(session):
    a, b, c = _notes(session, 3)
    ab = _link(session, a, b)
    assert relations.find(session, ab.id) is ab
    assert relations.find(session, 9999) is None
    assert relations.get_for_note(session, a.id, ab.id) is ab
    assert relations.get_for_note(session, b.id, ab.id) is ab
    with pytest.raises(NotFound) as err:
        relations.get_for_note(session, c.id, ab.id)
    assert err.value.detail == "That link could not be found."
    with pytest.raises(NotFound):
        relations.get_for_note(session, a.id, 9999)


def test_pairs_and_touching_read_the_stored_links(session):
    a, b, c = _notes(session, 3)
    ab, bc = _link(session, a, b), _link(session, b, c)
    assert sorted(relations.pairs(session)) == [(a.id, b.id), (b.id, c.id)]
    assert [r.id for r in relations.touching(session, b.id)] == [ab.id, bc.id]
    assert [r.id for r in relations.touching(session, a.id)] == [ab.id]
    assert relations.touching(session, 9999) == []


def test_with_type_and_untyped_split_on_the_link_type(session):
    a, b, c = _notes(session, 3)
    tension = _link(session, a, b, link_type="contradicts")
    first = _link(session, b, c)
    second = _link(session, a, c)
    assert [r.id for r in relations.with_type(session, "contradicts")] == [tension.id]
    assert [r.id for r in relations.untyped(session, limit=10)] == [second.id, first.id]
    assert [r.id for r in relations.untyped(session, limit=1)] == [second.id]


def test_among_and_touching_any_read_by_the_ids_asked_for(session):
    a, b, c = _notes(session, 3)
    _link(session, a, b, reason="why")
    _link(session, b, c)
    assert relations.among(session, [a.id, b.id]) == [(a.id, b.id, "why")]
    assert relations.among(session, []) == []
    assert relations.touching_any(session, {a.id}) == [(a.id, b.id)]
    assert relations.touching_any(session, {c.id}) == [(b.id, c.id)]
    newest_first = relations.touching_any(session, {a.id, c.id})
    assert newest_first == [(b.id, c.id), (a.id, b.id)]


def test_wiki_sources_are_the_notes_whose_stored_wiki_link_lands_on_the_target(session):
    a, b, c = _notes(session, 3)
    _link(session, a, c, origin="wiki")
    _link(session, b, c)
    assert relations.wiki_sources(session, c.id) == [a.id]
    assert relations.wiki_sources(session, a.id) == []


def test_counts_cover_every_link_and_live_links_leave_out_a_binned_end(session):
    a, b, c = _notes(session, 3)
    _link(session, a, b)
    _link(session, b, c)
    assert relations.count(session) == 2
    assert relations.count_live(session) == 2
    c.is_deleted = True
    session.flush()
    assert relations.count(session) == 2
    assert relations.count_live(session) == 1
    assert relations.newest(session) is not None


def test_columns_are_the_graphs_fields_and_all_gives_export_order(session):
    a, b, c = _notes(session, 3)
    first = _link(session, a, b, reason="r", link_type="supports", two_way=True)
    second = _link(session, b, c)
    rows = relations.columns(session, ordered=True)
    assert [r.id for r in rows] == [first.id, second.id]
    assert (rows[0].reason, rows[0].link_type, rows[0].two_way) == ("r", "supports", True)
    assert [r.id for r in relations.all_rows(session)] == [first.id, second.id]
