"""The local usage ledger (WORLD_CLASS_PLAN H9, row 27): which of the app's
features this person actually uses, counted on this computer only.

Never sent anywhere. Nothing in the app reports it, no route exposes it to
anything but the person's own signed-in page, and it holds names of
features and dates, never what was typed. It answers two questions the
person can see in Settings, General, What you use: which features have not
been used in ninety days (the first notebook that tells its owner which of
itself is dead weight), and which are used most (the command palette lists
those first).

**A file, not a table.** One small JSON file beside the database, written
atomically: the ledger is a few hundred counters read whole and written
whole, it needs no query, and a table would be a migration shared with every
other agent's branch for no gain. Deleting the file resets it, which Settings
offers as Clear.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import date, timedelta

from pathlib import Path

from tessellate.core import clock
from tessellate.core.atomic_io import atomic_write_text

#: A feature name: what the page sends. Short and plain so nothing typed can
#: ride along in one (`tab:notes`, `cmd:open-settings`).
NAME = re.compile(r"^[a-z0-9][a-z0-9:._-]{0,59}$")
MAX_FEATURES = 1000
UNUSED_DAYS = 90

_lock = threading.Lock()


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / "usage.json"


def read(data_dir: Path) -> dict[str, dict]:
    try:
        data = json.loads(_path(data_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record(data_dir: Path, names: list[str], today: date | None = None) -> int:
    """Count one use of each valid name. Returns how many were counted."""
    day = (today or clock.today()).isoformat()
    valid = [n for n in names if isinstance(n, str) and NAME.match(n)]
    if not valid:
        return 0
    with _lock:
        ledger = read(data_dir)
        for name in valid:
            row = ledger.get(name)
            if row is None:
                if len(ledger) >= MAX_FEATURES:
                    continue
                row = ledger[name] = {"count": 0, "first": day}
            row["count"] = int(row.get("count", 0)) + 1
            row["last"] = day
        atomic_write_text(_path(data_dir), json.dumps(ledger, sort_keys=True))
    return len(valid)


def summary(data_dir: Path, known: list[str] | None = None, today: date | None = None) -> dict:
    """The ledger, most used first, and the known features not used in
    `UNUSED_DAYS` days (never used counts as unused)."""
    ledger = read(data_dir)
    cutoff = ((today or clock.today()) - timedelta(days=UNUSED_DAYS)).isoformat()
    rows = sorted(
        ({"name": k, "count": int(v.get("count", 0)), "last": v.get("last"), "first": v.get("first")} for k, v in ledger.items()),
        key=lambda r: (-r["count"], r["name"]),
    )
    unused = [
        name for name in (known or [])
        if NAME.match(name) and (name not in ledger or str(ledger[name].get("last") or "") < cutoff)
    ]
    return {"features": rows, "unused": unused, "unused_days": UNUSED_DAYS}


def clear(data_dir: Path) -> None:
    with _lock:
        #: Nothing counted yet is already clear.
        _path(data_dir).unlink(missing_ok=True)
