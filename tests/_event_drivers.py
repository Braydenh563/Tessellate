"""The spec's drivers for `tests/test_events.py` (audit 2026-10-05, ARCH-21).

`test_every_manager_write_records_exactly_one_event` enumerates every public
write function in `entry/manager.py` by name prefix and asks this table to
exercise each one. The day someone adds a write, the enumeration finds it, no
driver is registered, and the test fails with a message saying what to do.
That guarantee is the test's, wherever the table lives: it lived in
`core/events.py` (150 lines shipped in the app for a test), and lives here.

Not named `test_*.py` on purpose, as `_app_js.py`.
"""

from __future__ import annotations

import importlib

from sqlalchemy.orm import Session

from tessellate.core.database import Entry
from tessellate.core.events import suppressed

def _scratch_entry(session: Session, content: str = "driver note") -> Entry:
    """A throwaway note for a driver to act on, recorded by nobody."""
    manager = importlib.import_module("tessellate.entry.manager")
    with suppressed():
        entry = manager.create_entry(session, content, tags=["driver"])
    return entry


def _drive_archive_entry(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager.archive_entry(session, _scratch_entry(session))


def _drive_create_entry(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    with suppressed():
        # So the category this note lands in already exists: creating it is
        # part of the same event, but the test counts rows, and a category
        # created here would make the count depend on what ran before.
        manager.get_or_create_category(session, manager.UNCATEGORISED)
    manager.create_entry(session, "a note the driver made", tags=[])


def _drive_create_link(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager.create_link(session, entry, _scratch_entry(session, "link target"))


def _document_for(session: Session):
    from tessellate.core.database import Document

    document = Document(title="driver document", content="")
    session.add(document)
    session.flush()
    return document


def _drive_link_document(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager.link_document(session, _document_for(session).id, entry.id)


def _drive_unlink_document(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    document = _document_for(session)
    with suppressed():
        manager.link_document(session, document.id, entry.id)
    manager.unlink_document(session, document.id, entry.id)


def _drive_purge_entries(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager_purge = importlib.import_module("tessellate.entry.manager_purge")
    doomed = [_scratch_entry(session, "purge me"), _scratch_entry(session, "purge me too")]
    with suppressed():
        for one in doomed:
            manager.soft_delete_entry(session, one)
    manager_purge.purge_entries(session, doomed)


def _drive_purge_expired_deleted(session: Session, entry: Entry) -> None:
    from datetime import timedelta

    from tessellate.core.database import utcnow

    manager = importlib.import_module("tessellate.entry.manager")
    manager_purge = importlib.import_module("tessellate.entry.manager_purge")
    expired = _scratch_entry(session, "binned long ago")
    with suppressed():
        manager.soft_delete_entry(session, expired)
        expired.deleted_at = utcnow() - timedelta(days=90)
        session.commit()
    manager_purge.purge_expired_deleted(session, days=30)


def _drive_record_dates(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager.record_dates(session, _scratch_entry(session, "the deadline is tomorrow"))


def _drive_record_revision(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager.record_revision(session, _scratch_entry(session, "a version worth keeping"))


def _drive_restore_entry(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    binned = _scratch_entry(session, "back from the bin")
    with suppressed():
        manager.soft_delete_entry(session, binned)
    manager.restore_entry(session, binned)


def _drive_soft_delete_entry(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager.soft_delete_entry(session, _scratch_entry(session, "into the bin"))


def _drive_unarchive_entry(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    archived = _scratch_entry(session, "out of the archive")
    with suppressed():
        manager.archive_entry(session, archived)
    manager.unarchive_entry(session, archived)


def _drive_record_filing(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager.record_filing(session, _scratch_entry(session), "Filed by the driver")


def _drive_update_entry(session: Session, entry: Entry) -> None:
    manager = importlib.import_module("tessellate.entry.manager")
    manager.update_entry(session, _scratch_entry(session), content="edited by the driver")


_DRIVERS = {
    "archive_entry": _drive_archive_entry,
    "create_entry": _drive_create_entry,
    "create_link": _drive_create_link,
    "link_document": _drive_link_document,
    "purge_entries": _drive_purge_entries,
    "purge_expired_deleted": _drive_purge_expired_deleted,
    "record_dates": _drive_record_dates,
    "record_filing": _drive_record_filing,
    "record_revision": _drive_record_revision,
    "restore_entry": _drive_restore_entry,
    "soft_delete_entry": _drive_soft_delete_entry,
    "unarchive_entry": _drive_unarchive_entry,
    "unlink_document": _drive_unlink_document,
    "update_entry": _drive_update_entry,
}


def exercise_for_test(session: Session, name: str, entry: Entry) -> None:
    """Call one manager write the way the spec needs it called.

    Each driver sets up whatever that write needs with events suppressed, so
    the one event the test counts is the write's own.
    """
    driver = _DRIVERS.get(name)
    if driver is None:
        raise NotImplementedError(
            f"{name} is a public write in entry/manager.py with no driver in "
            "tests/_event_drivers.py. Make it record exactly one event (wrap it in "
            "@events.writes and give its log_action a whole-field payload), "
            "then register a driver for it in tests/_event_drivers.py's _DRIVERS."
        )
    driver(session, entry)
