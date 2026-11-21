"""Read the dates in notes saved before `timewords` could read them.

`timewords` learned written-out dates (2026-10-25, 16 October 2026) in
TIMELINE_PLAN decision 21. A note saved before that has no row for them, so
the Timeline and the calendar kept it on the day it was typed. This reads them
again, once, as a background job.

**Idempotent**: a note is rewritten only when its text now yields a phrase that
is not stored yet, so a second pass over the same notes changes nothing.
**Resumable**: the last note id done is kept in a preference after every chunk,
so a quit part way continues from there. **It drains to done**: when no note
is left the version preference is set and the job never queues again.

The reference day is the note's own `created_at`, not today: "tomorrow" in an
old note is a day near it, and a re-read must not move it.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from tessellate.core import deps, jobruns
from tessellate.core.database import Entry, EntryDate, impersonate_workspace
from tessellate.entry import manager, timewords

logger = logging.getLogger("tessellate.redate")

#: Raised when `timewords` learns to read something new; a notebook whose
#: stored version is lower is read again.
VERSION = 4  # 4: a range's last day (`until`), which rows saved before the column lack
DONE_KEY = "dates_read_version"
CURSOR_KEY = "dates_read_cursor"
CHUNK = 200


def pending() -> bool:
    """Whether notes still need reading (the stored version is behind)."""
    try:
        return int(deps.get_config().get_preference(DONE_KEY, 0) or 0) < VERSION
    except (TypeError, ValueError):
        return True


def _reread(session, entry: Entry) -> bool:
    """Store the dates this note's text yields now. True when it changed."""
    if entry.is_private or not entry.content or entry.created_at is None:
        return False
    #: The phrase and the day it meant: a weekday read as the coming one
    #: before `timewords` knew it said it happened is read again (INBOX 1668).
    #: And a range's last day: a row saved before `until` existed has none.
    stored = {
        (phrase, at.date(), until.date() if until else None)
        for phrase, at, until in session.execute(select(EntryDate.phrase, EntryDate.at, EntryDate.until).where(EntryDate.entry_id == entry.id))
    }
    found = timewords.find(entry.content, entry.created_at)
    if not any((mention.phrase[:60], mention.at, mention.until) not in stored for mention in found):
        return False
    manager.record_dates(session, entry, now=entry.created_at)
    return True


def run(chunk: int = CHUNK) -> dict:
    """Read the dates of every note not yet dated, in chunks, committing and
    recording the cursor after each. Returns {"notes", "changed", "done"}."""
    config = deps.get_config()
    cursor = int(config.get_preference(CURSOR_KEY, 0) or 0)
    seen = changed = 0
    with jobruns.job_run("redate") as record:
        with deps.get_db().session() as session, impersonate_workspace(session, "all"):
            total = session.scalar(select(func.count(Entry.id)).where(Entry.id > cursor)) or 0
            record.step(0, total, "Reading dates in notes")
            record.say(f"{total} note{'' if total == 1 else 's'} to read.")
            while True:
                rows = session.scalars(
                    select(Entry).where(Entry.id > cursor).order_by(Entry.id).limit(max(1, chunk))
                ).all()
                if not rows:
                    break
                for entry in rows:
                    try:
                        changed += int(_reread(session, entry))
                    except Exception:  # noqa: BLE001  # one note must not stop the pass
                        logger.warning("couldn't read the dates in note %s", entry.id, exc_info=True)
                cursor = rows[-1].id
                seen += len(rows)
                session.commit()
                config.set_preference(CURSOR_KEY, cursor)
                record.step(seen, total)
        config.set_preference(DONE_KEY, VERSION)
        config.set_preference(CURSOR_KEY, 0)
        record.result = f"read {seen} note{'' if seen == 1 else 's'}, {changed} placed by a date they name"
    return {"notes": seen, "changed": changed, "done": True}


def enqueue_if_pending() -> bool:
    """Queue the pass when notes are still to read. Called at start-up."""
    if not pending():
        return False
    from tessellate.core import jobs

    jobs.enqueue("redate", run, dedupe_key="redate", name="reading dates in notes")
    return True
