"""A link row never outlives either of its notes (audit G16, notes audit N13).

The diagnostics report said "37 notes, 4,234 links" after 1,500 notes were
deleted through the API. Two parts: the count included the links of binned
notes (the graph shows none of them), and nothing proved that a purge or a
startup clears links whose note is truly gone. Fixed clock: `created_at` is
given, never read from the real one.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from tessellate.api import routes_diag
from tessellate.core import deps
from tessellate.core.database import DatabaseManager, Entry, EntryLink

NOW = datetime(2026, 10, 29, 9, 0, tzinfo=timezone.utc)


def _note(session, content):
    entry = Entry(content=content)
    session.add(entry)
    session.commit()
    return entry


def _link(session, a, b, workspace="default"):
    session.add(EntryLink(source_entry_id=a.id, target_entry_id=b.id, created_at=NOW, workspace_id=workspace))
    session.commit()


def _links(session) -> int:
    return session.scalar(select(func.count()).select_from(EntryLink.__table__))


def test_startup_removes_links_whose_note_is_gone(tmp_path):
    path = tmp_path / "orphans.db"
    first = DatabaseManager(path)
    with first.session() as session:
        a, b = _note(session, "kept a"), _note(session, "kept b")
        _link(session, a, b)
        session.commit()
        ids = (a.id, b.id)
    with first.engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for source, target in ((ids[0], 9001), (9002, ids[1]), (9003, 9004)):
            connection.exec_driver_sql(
                "INSERT INTO entry_links (source_entry_id, target_entry_id, created_at, workspace_id)"
                " VALUES (?, ?, '2026-10-29 09:00:00', 'default')",
                (source, target),
            )
    first.engine.dispose()

    second = DatabaseManager(path)
    with second.session() as session:
        rows = session.execute(select(EntryLink.source_entry_id, EntryLink.target_entry_id)).all()
    assert [tuple(r) for r in rows] == [ids]
    second.engine.dispose()
    # A second start finds nothing more to do.
    third = DatabaseManager(path)
    with third.session() as session:
        assert _links(session) == 1
    third.engine.dispose()


def test_purge_clears_links_stamped_for_another_space(client, session):
    keep, goner = _note(session, "stays"), _note(session, "goes")
    _link(session, goner, keep, workspace="elsewhere")
    client.delete(f"/entries/{goner.id}")
    purged = client.delete(f"/entries/{goner.id}/purge")
    assert purged.status_code == 200
    session.expire_all()
    assert _links(session) == 0


def test_the_diagnostics_link_count_leaves_out_binned_notes(client, session):
    a, b, c = _note(session, "a"), _note(session, "b"), _note(session, "c")
    _link(session, a, b)
    _link(session, b, c)
    client.delete(f"/entries/{c.id}")
    routes_diag._counts.update(at=0.0, value=None)
    with deps.get_db().session() as fresh:
        assert routes_diag.counts(fresh)["links"] == 1
