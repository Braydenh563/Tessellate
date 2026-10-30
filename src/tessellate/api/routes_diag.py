"""`GET /diagnostics`: the server's half of the copyable diagnostics report
(INBOX 1430; Settings, Logs, Copy diagnostics, frontend/js/diag-report.js).

Counts, versions and the ring buffers of `core/diagring.py`, as JSON the page
turns into one plain-text report. Everything here is a number, a route, a
statement shape or a frame: no note text, no title, no query string, no
absolute path under the home folder (`diagring.redact`).
"""

from __future__ import annotations

import platform
import sys
import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from tessellate import __version__
from tessellate.core import deps, diagring, jobruns, lagwatch, maintenance
from tessellate.core.database import Document, Entry, EntryLink
from tessellate.entry import manager
from tessellate.core.deps import get_session

router = APIRouter(tags=["logs"])

#: Counts are four COUNT(*) queries; a lag report needs them as context, not fresh.
COUNTS_TTL_S = 60
_counts: dict = {"at": 0.0, "value": {}}

#: The settings that change what the app costs; the rest are described in the support bundle.
SETTINGS_THAT_MATTER = ("ai_enabled", "embedding_backend", "llm_provider", "local_only_ai", "thinking_enabled", "auto_categorise", "web_search_enabled")


def counts(session: Session) -> dict:
    """Notes, boards, documents and links, cached for a minute (a lag report asks per event)."""
    now = time.monotonic()
    if _counts["value"] and now - _counts["at"] < COUNTS_TTL_S:
        return _counts["value"]
    try:
        live_from, live_to = aliased(Entry), aliased(Entry)
        boards = session.scalar(
            select(func.count(Entry.id)).where(Entry.is_deleted == False, Entry.board_settings.is_not(None))  # noqa: E712
        ) or 0
        value = {
            "notes": manager.count_notes(session),
            "boards": boards,
            "docs": session.scalar(select(func.count(Document.id)).where(Document.deleted_at.is_(None))) or 0,
            #: Links between notes still in the notebook, the graph's own count: a binned
            #: note keeps its links for a restore, and counting them said 4,234 on 37 notes.
            "links": session.scalar(
                select(func.count(EntryLink.id))
                .join(live_from, live_from.id == EntryLink.source_entry_id)
                .join(live_to, live_to.id == EntryLink.target_entry_id)
                .where(live_from.is_deleted == False, live_to.is_deleted == False)  # noqa: E712
            )
            or 0,
        }
    except Exception:  # noqa: BLE001  # context for a report must never fail the report
        return _counts["value"]
    _counts.update(at=now, value=value)
    return value


#: app.py registers the asset-hash lookup at startup, so this module never imports app (a cycle).
BUILD: dict = {"hash": lambda: ""}


def context(session: Session) -> dict:
    """What every lag line carries from this side: sizes, app version, asset hash."""
    return {**counts(session), "v": __version__, "build": BUILD["hash"]() or ""}


def _job_failures() -> list[dict]:
    rows = [r for r in jobruns.finished() if r.get("outcome") == "failed"][:8]
    return [{"kind": r["kind"], "at": r.get("at", ""), "detail": diagring.redact(r.get("detail", ""), 160)} for r in rows]


def _settings() -> dict:
    prefs = deps.get_config().all_preferences()
    return {key: prefs.get(key) for key in SETTINGS_THAT_MATTER if key in prefs}


@router.get("/diagnostics")
def diagnostics(session: Session = Depends(get_session)) -> dict:
    logs_dir = maintenance.logs_dir(deps.get_config().data_dir)
    return {
        "version": __version__,
        "platform": diagring.redact(platform.platform(), 120),
        "python": sys.version.split()[0],
        "counts": counts(session),
        "settings": _settings(),
        "slow_routes": diagring.slow_routes(),
        "slow_queries": diagring.slow_queries(),
        "exceptions": diagring.exceptions(),
        "job_failures": _job_failures(),
        "lag": lagwatch.recent(logs_dir, 400),
    }
