"""The import report (WORLD_CLASS_PLAN 25b, Brief 48): what one import read,
wrote, skipped and merged, with every skipped item named and why.

Before this the whole record of an import was a status line and a toast,
and a skip past the second was "Left out 14: a; b." with the other twelve
gone. A report is kept as a small JSON file in `<data>/import-reports/`, so
it outlives the toast and a restart: the last `KEEP` stay, the oldest go.
The status line when the import ends and the Activity panel's finished line
open it (`GET /import/reports/{id}`).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tessellate.core import paths

KEEP = 20
#: A report lists every skip; this only stops a pathological export from
#: writing a file the page cannot draw.
MAX_ITEMS = 10000
_ID = re.compile(r"^[0-9]{8}-[0-9]{12}-[a-z]{1,12}$")


def folder(data_dir: Path) -> Path:
    return Path(data_dir) / "import-reports"


def _item(line: str) -> dict:
    """"name: reason" as two fields; a line with no name is all reason."""
    name, sep, reason = str(line).rpartition(": ")
    return {"name": name, "reason": reason} if sep else {"name": "", "reason": str(line)}


def build(*, source: str, label: str, files: int, read, written: dict, seconds: float, stopped: bool) -> dict:  # noqa: ANN001
    skipped = [_item(line) for line in read.skipped[:MAX_ITEMS]]
    return {
        "source": source,
        "label": label,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "seconds": round(seconds, 2),
        "stopped": stopped,
        "counts": {
            "files": files,
            "read": len(read.notes),
            "written": written.get("imported", 0),
            "skipped": len(read.skipped),
            "merged": written.get("already", 0),
            "documents": written.get("documents", 0),
        },
        "skipped": skipped,
        "notes": [_item(line) for line in (written.get("said") or [])[:MAX_ITEMS]],
    }


def save(data_dir: Path, report: dict) -> str:
    """Write it and drop the oldest past `KEEP`. Returns its id."""
    where = folder(data_dir)
    where.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%f")
    report_id = f"{stamp}-{re.sub('[^a-z]', '', report['source'])[:12] or 'import'}"
    report["id"] = report_id
    _inside(where, report_id).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    for old in sorted(where.glob("*.json"))[:-KEEP]:
        old.unlink(missing_ok=True)
    return report_id


def latest(data_dir: Path) -> str:
    """The newest kept report's id, or "" (the Background jobs Report button)."""
    kept = sorted(folder(data_dir).glob("*.json")) if folder(data_dir).is_dir() else []
    return kept[-1].stem if kept else ""


def _inside(where: Path, report_id: str) -> Path:
    """The report's file, refused unless it resolves inside the reports folder
    (the id is checked by shape too; this is the check a path needs)."""
    try:
        return paths.contained(where, f"{report_id}.json")
    except paths.OutsideFolder:
        raise ValueError("not a report of this notebook") from None


def load(data_dir: Path, report_id: str) -> dict | None:
    if not _ID.match(report_id or ""):
        return None
    try:
        path = _inside(folder(data_dir), report_id)
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
