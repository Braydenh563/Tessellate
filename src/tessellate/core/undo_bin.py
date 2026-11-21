"""The undo bin: what a delete took with it, kept so Undo can put it back.

INBOX 898 ("make sure that the undo and redo are properly and completely
universal"). Notes, documents, reminders and boards already have a soft delete
and a restore route. A file, a picture, a past question, a learned fact and a
board library did not: the row (and the bytes) were gone for good, so the
browser had nothing to undo with.

A delete route calls `stash` before it removes anything and returns the
token; the matching `POST .../restore` calls `take` with it. Nothing here
knows about a table: the caller hands over a plain dict (rows go through
`row_dict`) and the files it wants kept, and gets the same back.

Kept on disk under `<data dir>/undo-bin/<token>/`, so a restart does not
lose the way back, and pruned by age (`KEEP_DAYS`) the next time anything is
stashed. The folder is not part of a backup: it is a second chance, not a
copy. A token is an unguessable hex string and is checked as one before it
names a path.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import inspect

from tessellate.core import paths

FOLDER = "undo-bin"
#: How long a deleted thing can still be brought back. Long enough for a
#: session kept running over a weekend, short enough that the bin never becomes a
#: second copy of the notebook.
KEEP_DAYS = 14
_TOKEN = re.compile(r"^[0-9a-f]{32}$")


def _root(data_dir: Path) -> Path:
    return Path(data_dir) / FOLDER


def _folder(data_dir: Path, token: str) -> Path:
    if not isinstance(token, str) or not _TOKEN.match(token):
        raise HTTPException(status_code=404, detail="That can no longer be put back.")
    try:
        return paths.contained(_root(data_dir), token)
    except paths.OutsideFolder:
        raise HTTPException(status_code=404, detail="That can no longer be put back.") from None


def prune(data_dir: Path, days: int = KEEP_DAYS) -> int:
    """Remove stashes older than `days`. Returns how many went."""
    root = _root(data_dir)
    if not root.is_dir():
        return 0
    cutoff = time.time() - days * 86400
    gone = 0
    for folder in root.iterdir():
        try:
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
                gone += 1
        except OSError:
            continue
    return gone


def stash(
    data_dir: Path,
    kind: str,
    payload: dict[str, Any],
    files: dict[str, Path] | None = None,
) -> str:
    """Keep `payload` (JSON-safe) and move each of `files` (`{name: path}`) into the bin.

    A file that is not there is skipped, so a row whose bytes were already
    lost can still be put back as a row. Returns the token.
    """
    prune(data_dir)
    token = uuid.uuid4().hex
    folder = _folder(data_dir, token)
    folder.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    for name, source in (files or {}).items():
        source = Path(source)
        if not source.is_file():
            continue
        shutil.move(str(source), str(folder / f"file-{len(kept)}"))
        kept.append(name)
    (folder / "stash.json").write_text(
        json.dumps({"kind": kind, "payload": payload, "files": kept}), encoding="utf-8"
    )
    return token


def take(data_dir: Path, kind: str, token: str) -> tuple[dict[str, Any], dict[str, Path]]:
    """The payload and the kept files (`{name: path in the bin}`) for `token`.

    Raises 404 for a token that is unknown, expired or of another kind. The
    caller moves the files back, then calls `finish`.
    """
    folder = _folder(data_dir, token)
    record = folder / "stash.json"
    if not record.is_file():
        raise HTTPException(status_code=404, detail="That can no longer be put back.")
    data = json.loads(record.read_text(encoding="utf-8"))
    if data.get("kind") != kind:
        raise HTTPException(status_code=404, detail="That can no longer be put back.")
    files = {name: folder / f"file-{i}" for i, name in enumerate(data.get("files", []))}
    return data["payload"], files


def finish(data_dir: Path, token: str) -> None:
    """Drop a stash that has been put back."""
    shutil.rmtree(_folder(data_dir, token), ignore_errors=True)


def _plain(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return {"$dt": value.isoformat()}
    if isinstance(value, (bytes, bytearray)):
        return {"$b64": base64.b64encode(bytes(value)).decode("ascii")}
    return value


def _back(value: Any) -> Any:
    if isinstance(value, dict) and "$dt" in value:
        return datetime.fromisoformat(value["$dt"])
    if isinstance(value, dict) and "$b64" in value:
        return base64.b64decode(value["$b64"])
    return value


def row_dict(row: Any) -> dict[str, Any]:
    """Every column of an ORM row as JSON-safe values (datetimes and bytes tagged)."""
    return {c.key: _plain(getattr(row, c.key)) for c in inspect(type(row)).mapper.column_attrs}


def row_from(model: type, data: dict[str, Any], *, keep_id: bool = True) -> Any:
    """A new `model` row from `row_dict` output; `keep_id=False` lets the table pick an id."""
    columns = {c.key for c in inspect(model).mapper.column_attrs}
    values = {k: _back(v) for k, v in data.items() if k in columns}
    if not keep_id:
        values.pop("id", None)
    return model(**values)
