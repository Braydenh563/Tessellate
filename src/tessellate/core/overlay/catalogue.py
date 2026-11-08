"""The companion catalogue as the desk reads it (INBOX 1696 dd, v, kk; atlascat-1108 step 4).

`frontend/companion-catalogue.json` is one table both companions draw from: the app fetches it as
`/companion-catalogue.json`, the desk reads the same file through `FRONTEND_DIR`. A missing or broken
file is an empty table, so the built-in tables stand and nothing else changes. Read once, cached.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


def path() -> Path:
    """`frontend/companion-catalogue.json`, in a checkout or a bundled build (the root `api/app.py` names
    `FRONTEND_DIR` from; not imported, since `behaviour.py` reads this at import and the app is heavy)."""
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        root = Path(__file__).resolve().parents[4]
    return root / "frontend" / "companion-catalogue.json"


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    """The whole document, or `{}` when the file is missing or not a JSON object."""
    try:
        doc = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def entries() -> list[dict[str, Any]]:
    rows = load().get("entries", [])
    return [e for e in rows if isinstance(e, dict) and "id" in e] if isinstance(rows, list) else []


@lru_cache(maxsize=1)
def by_desk_name() -> dict[str, dict[str, Any]]:
    """Each act entry built on the desk, by the desk table name it covers (`acts:doze` -> `doze`)."""
    out: dict[str, dict[str, Any]] = {}
    for e in entries():
        if e.get("kind") != "idle_act" or e.get("desk", {}).get("s") != "built":
            continue
        for n in e["desk"].get("names", []):
            table, _, name = n.partition(":")
            if table == "acts":
                out[name] = e
    return out


def reset() -> None:
    """Forget what was read (a test that points `path` elsewhere)."""
    load.cache_clear()
    by_desk_name.cache_clear()
