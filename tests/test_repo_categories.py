"""The categories repository's reads, against a real session (INBOX 1499).

The category routes' own tests hold the routes unchanged; these hold the
repository: a row by id, a name by id, the names, the rows in id order, the
count, a live count per name and the name of each note's category.
"""

from __future__ import annotations

from tessellate.core.database import Category, Entry
from tessellate.repo import categories


def _category(session, name: str) -> Category:
    row = Category(name=name)
    session.add(row)
    session.flush()
    return row


def _note(session, category: Category | None, **kw) -> Entry:
    entry = Entry(content="n", category_id=category.id if category else None, **kw)
    session.add(entry)
    session.flush()
    return entry


def test_find_and_name_of_read_one_category(session):
    travel = _category(session, "Travel")
    assert categories.find(session, travel.id) is travel
    assert categories.find(session, 9999) is None
    assert categories.name_of(session, travel.id) == "Travel"
    assert categories.name_of(session, 9999) is None
    assert categories.name_of(session, None) is None


def test_names_rows_and_count_cover_every_category(session):
    a, b = _category(session, "Work"), _category(session, "Home")
    assert {"Home", "Work"} <= set(categories.names(session))
    ours = [c.id for c in categories.all_rows(session) if c.id in (a.id, b.id)]
    assert ours == [a.id, b.id]
    assert [(i, n) for i, n in categories.id_names(session) if i in (a.id, b.id)] == [(a.id, "Work"), (b.id, "Home")]
    assert categories.count(session) == len(categories.all_rows(session))


def test_note_counts_group_live_notes_by_name_biggest_first(session):
    work, home = _category(session, "WorkX"), _category(session, "HomeX")
    _note(session, work)
    _note(session, work)
    _note(session, home)
    _note(session, home, is_deleted=True)
    _note(session, None)
    rows = categories.note_counts(session, Entry.is_deleted == False)  # noqa: E712
    got = {name: n for name, n in rows}
    assert got["WorkX"] == 2 and got["HomeX"] == 1
    assert [n for _name, n in rows] == sorted((n for _name, n in rows), reverse=True)
    everything = {name: n for name, n in categories.note_counts(session)}
    assert everything["HomeX"] == 2


def test_names_by_entry_and_by_id_skip_what_has_no_category(session):
    work = _category(session, "WorkY")
    a, b = _note(session, work), _note(session, None)
    assert categories.names_by_entry(session, [a.id, b.id]) == {a.id: "WorkY"}
    assert categories.names_by_entry(session, []) == {}
    assert categories.names_by_id(session, {work.id}) == {work.id: "WorkY"}
    assert categories.names_by_id(session, set()) == {}
