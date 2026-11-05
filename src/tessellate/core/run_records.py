"""The per-user records behind Settings, Running copies (INBOX 1641).

A leaf: `instance_lock` writes and removes this server's record here, and
`running_copies` reads them, so neither imports the other. One `<pid>.json`
per running server in a folder only this user can read
(`%LOCALAPPDATA%\\Tessellate\\run` on Windows, `$XDG_STATE_HOME/tessellate/run`
elsewhere; `TESSELLATE_RUN_DIR` overrides it, which the tests use).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Record:
    pid: int
    port: int
    token: str
    started: float
    data_dir: str = ""


def run_dir() -> Path:
    override = os.environ.get("TESSELLATE_RUN_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Tessellate" / "run"
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "tessellate" / "run"


def path_for(pid: int) -> Path:
    return run_dir() / f"{int(pid)}.json"


def register(record: Record) -> None:
    from tessellate.core.atomic_io import atomic_write_text

    folder = run_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(folder, 0o700)  # the files are 0600 already; the listing is private too
    atomic_write_text(path_for(record.pid), json.dumps(asdict(record)))


def unregister(pid: int, token: str) -> None:
    """Remove a record, and only if it is still the one with this token."""
    current = read(path_for(pid))
    if current is not None and current.token == token:
        try:
            path_for(pid).unlink()
        except OSError:
            pass  # already gone, or the folder is read-only: the next listing prunes it


def read(path: Path) -> Record | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rec = Record(
            pid=int(raw["pid"]),
            port=int(raw["port"]),
            token=str(raw["token"]),
            started=float(raw["started"]),
            data_dir=str(raw.get("data_dir", "")),
        )
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None
    if not 1 <= rec.port <= 65535 or not rec.token or rec.pid <= 0:
        return None
    return rec
