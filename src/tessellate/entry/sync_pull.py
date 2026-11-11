"""Sync now: pull the other computer's segments until its log is drained (WORLD_CLASS_PLAN B6).

Decision 9: the transport is one object, `name` (the other computer's device
id, learned at pairing) and `fetch(since, me)` returning a segment (with
`manifest`, `items` and `file` for documents, boards and files, decision
13), so the LAN fetch, the tests' fake and a later shared-folder transport
share this loop and `sync_segments.apply_segment`. A transport raises `OSError` when
the other computer does not answer.

The cursor moves only after a whole segment has been applied, and an apply
cut off part way is applied again from the same cursor: each note's apply is
a no-op the second time (decision 8).

The LAN fetch is `entry/sync_link.py` (decisions 10 and 11): once pairing
has stored a pass, `transport` reads it from disk. Until then Sync now
answers `NOT_PAIRED`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Protocol

from sqlalchemy.orm import Session

from tessellate.core import sync_state
from tessellate.entry import sync_keys, sync_link
from tessellate.entry.sync_extras_apply import pull_extras
from tessellate.entry.sync_segments import DAMAGED, SegmentError, apply_segment

logger = logging.getLogger("tessellate.sync")

NOT_PAIRED = "No other computer is paired for sync yet; this one is unchanged."
OFFLINE = "The other computer did not answer; nothing changed here."
STOPPED = "Sync stopped part way; Sync now picks up where it stopped."
WRONG_PEER = "The answer came from a different computer than the paired one; nothing was applied."
#: A log longer than this many segments is pulled over more than one press.
MAX_ROUNDS = 500


class Transport(Protocol):
    name: str

    def fetch(self, since: int, me: str) -> dict: ...

    def manifest(self, me: str) -> dict: ...

    def items(self, kind: str, sids: list[str], me: str) -> list: ...

    def file(self, sid: str, me: str) -> bytes | None: ...


#: Another way to reach the paired computer, tried before the stored LAN link (the tests' fake).
_transport: Callable[[], Transport | None] = lambda: None  # noqa: E731  # only the LAN link so far


def use_transport(factory: Callable[[], Transport | None]) -> None:
    """Register how this notebook reaches the paired computer."""
    global _transport
    _transport = factory


def transport(data_dir: Path) -> Transport | None:
    registered = _transport()
    return registered if registered is not None else sync_link.load(data_dir)


def _round(session: Session, data_dir: Path, link: Transport, me: str, totals: dict) -> bool:
    """One segment pulled and applied; True while the other computer has more."""
    since = sync_state.peer(data_dir, link.name)["cursor"]
    segment = link.fetch(since, me)
    if not isinstance(segment, dict) or segment.get("device") != link.name:
        raise SegmentError(WRONG_PEER if isinstance(segment, dict) else DAMAGED)
    for key, count in apply_segment(session, me, segment, sync_keys.keys(data_dir)).items():
        totals[key] += count
    sync_state.save_peer(data_dir, link.name, cursor=segment["upto"])
    return bool(segment.get("more")) and segment["upto"] > since


def _drain(session: Session, data_dir: Path, link: Transport, totals: dict) -> str:
    """Pull until the other computer has nothing more; the failure sentence, or ''."""
    me = sync_state.device_id(data_dir)
    try:
        for _ in range(MAX_ROUNDS):
            if not _round(session, data_dir, link, me, totals):
                break
        # Decision 13: documents, boards and files, by state, once the notes are in.
        for key, count in pull_extras(session, data_dir, link, me, sync_keys.keys(data_dir)).items():
            totals[key] = totals.get(key, 0) + count
        return ""
    except SegmentError as exc:
        return str(exc)
    except OSError:
        return OFFLINE
    except Exception:  # noqa: BLE001  # logged; the sentence is the person's answer, the cursor stays
        logger.exception("sync: a pull stopped part way")
        session.rollback()
        return STOPPED


def pull(session: Session, data_dir: Path) -> dict:
    """Sync now: pull from the paired computer and record how it ended."""
    link = transport(data_dir)
    if link is None:
        return {**status(data_dir), "error": NOT_PAIRED}
    totals = {"applied": 0, "same": 0, "conflicts": 0}
    error = _drain(session, data_dir, link, totals)
    done = {"error": error, "last": totals}
    if not error:
        done["synced_at"] = time.time()
    sync_state.save_peer(data_dir, link.name, **done)
    return status(data_dir)


def status(data_dir: Path) -> dict:
    """The Settings line: when the last pull ended well, its counts, and its failure sentence."""
    found = sync_state.last_peer(data_dir)
    row = found[1] if found else {}
    last = row.get("last") if isinstance(row.get("last"), dict) else {}
    stored = sync_state.link(data_dir) if transport(data_dir) is not None else {}
    return {
        "paired": bool(stored) or _transport() is not None,
        "address": f"{stored['host']}:{stored['port']}" if stored else "",
        "fingerprint": stored.get("fingerprint", ""),
        "private_readable": bool(stored.get("peer_key")),
        "synced_at": row.get("synced_at"),
        "error": row.get("error") or "",
        "applied": int(last.get("applied") or 0),
        "conflicts": int(last.get("conflicts") or 0),
    }
