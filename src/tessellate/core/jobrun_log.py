"""The Activity History's store across restarts (`JobRunLog`), split out of
`jobruns.py` for its file size cap. `jobruns` resolves the database and
passes it in; nothing here raises, since the ring still holds every run."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

#: What the History tab keeps across restarts (`JobRunLog`): the newest rows
#: and nothing older than the days, by the person's own clock.
KEEP_ROWS = 500
KEEP_DAYS = 30


def logged_now() -> datetime:
    """Now on the person's own clock, naive: what `JobRunLog.logged_at` holds."""
    from tessellate.core import config

    return config.loaded_user_now().replace(tzinfo=None)


def persist(entry: dict, replaced: str, db, clip, keep_rows: int = KEEP_ROWS, keep_days: int = KEEP_DAYS) -> None:  # noqa: ANN001
    """Write one finished run to `job_run_log` and prune it. `replaced` is the
    run id a merged row stands in for. Never raises: the ring still has it."""
    if db is None:
        return
    try:
        from sqlalchemy import delete, func, select

        from tessellate.core.database import JobRunLog

        now = logged_now()
        with db.session() as session:
            if replaced:
                session.execute(delete(JobRunLog).where(JobRunLog.run_id == replaced))
            session.merge(
                JobRunLog(
                    run_id=entry["run_id"], kind=entry["kind"], title=clip(entry["title"]),
                    label=clip(entry["label"]), origin=entry["origin"], why=clip(entry["why"]),
                    outcome=entry["outcome"], detail=clip(entry["detail"]), started=entry["started"],
                    ended=entry["ended"], duration_ms=entry["duration_ms"], count=entry["count"],
                    lines=entry["lines"], logged_at=now,
                )
            )
            session.flush()
            session.execute(delete(JobRunLog).where(JobRunLog.logged_at < now - timedelta(days=keep_days)))
            if session.scalar(select(func.count()).select_from(JobRunLog)) > keep_rows:
                keep = select(JobRunLog.run_id).order_by(JobRunLog.ended.desc()).limit(keep_rows)
                session.execute(delete(JobRunLog).where(JobRunLog.run_id.not_in(keep)))
            session.commit()
    except Exception:  # noqa: BLE001  # the history is a convenience, never a reason to fail a run
        logger.debug("could not keep the run history", exc_info=True)


def forget(db) -> None:  # noqa: ANN001
    if db is None:
        return
    try:
        from sqlalchemy import delete

        from tessellate.core.database import JobRunLog

        with db.session() as session:
            session.execute(delete(JobRunLog))
            session.commit()
    except Exception:  # noqa: BLE001
        logger.debug("could not clear the run history", exc_info=True)


def stored(limit: int, db, seen: set) -> list[dict]:  # noqa: ANN001
    """The stored runs newest first, but those in `seen` (the ring holds a fresher copy)."""
    found: list[dict] = []
    if db is not None:
        try:
            from sqlalchemy import select

            from tessellate.core.database import JobRunLog

            with db.session() as session:
                rows = session.scalars(select(JobRunLog).order_by(JobRunLog.ended.desc()).limit(limit))
                for row in rows:
                    if row.run_id in seen:
                        continue
                    found.append(
                        {
                            "run_id": row.run_id, "kind": row.kind, "name": "", "label": row.label,
                            "title": row.title, "origin": row.origin, "why": row.why,
                            "outcome": row.outcome, "detail": row.detail, "started": row.started,
                            "ended": row.ended, "duration_ms": row.duration_ms,
                            "lines": list(row.lines or []), "count": row.count,
                        }
                    )
        except Exception:  # noqa: BLE001
            logger.debug("could not read the run history", exc_info=True)
    return found
