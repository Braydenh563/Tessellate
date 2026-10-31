"""Lag reports from the browser, kept on disk (the owner, 2026-10-26).

"can you make the app detect lag spikes or complexity issues ... and then it
logs it and the cause or when it happened ... so if it happens then I can give
you the logs?" The browser's watcher (frontend/js/lag-watch.js) sees a frame
that blocked, a slow interaction or a slow request and names its cause; this
keeps each one as a JSON line in `<data dir>/logs/lag.log`, the folder
Settings, Maintenance already opens, so a report survives a reload or a
restart and can be sent as a file. The in-memory log ring keeps 500 records
and loses them on restart, which is exactly when a lag report is wanted.

Bounded twice: each field is cut to a length here, and the file rolls to
`lag.log.1` past `MAX_BYTES`, so a page stuck in a slow loop cannot fill the
disk.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from tessellate.core import logbuffer

MAX_BYTES = 512 * 1024
FILE_NAME = "lag.log"
_lock = threading.Lock()


def log_path(logs_dir: Path) -> Path:
    return Path(logs_dir) / FILE_NAME


def clean(event: dict) -> dict:
    """The event with every value a short, single-line string or a number."""
    out: dict = {}
    for key, value in list(event.items())[:24]:
        name = logbuffer.safe_value(str(key), limit=40)
        if isinstance(value, bool) or value is None:
            out[name] = value
        elif isinstance(value, (int, float)):
            out[name] = round(float(value), 1)
        else:
            out[name] = logbuffer.safe_value(str(value), limit=400)
    return out


def append(logs_dir: Path, events: list[dict]) -> int:
    """Write the events as JSON lines, rolling the file first when it is full."""
    path = log_path(logs_dir)
    lines = "".join(json.dumps(clean(e), ensure_ascii=False) + "\n" for e in events)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size + len(lines) > MAX_BYTES:
            path.replace(path.with_name(FILE_NAME + ".1"))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(lines)
    return len(events)


def recent(logs_dir: Path, limit: int = 200) -> list[dict]:
    """The newest `limit` reports, oldest first, skipping a torn last line."""
    path = log_path(logs_dir)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        tail = fh.readlines()[-limit:]
    out = []
    for line in tail:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def clear(logs_dir: Path) -> None:
    with _lock:
        for name in (FILE_NAME, FILE_NAME + ".1"):
            (Path(logs_dir) / name).unlink(missing_ok=True)
