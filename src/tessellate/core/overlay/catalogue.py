"""The companion catalogue as the desk reads it (INBOX 1696 dd, v, kk; atlascat-1108 step 4).

`frontend/companion-catalogue.json` is one table both companions draw from: the app fetches it as
`/companion-catalogue.json`, the desk reads the same file through `FRONTEND_DIR`. A missing or broken
file is an empty table, so the built-in tables stand and nothing else changes. Read once, cached.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def path() -> Path:
    """`frontend/companion-catalogue.json`, in a checkout or a bundled build."""
    from tessellate.api.app import FRONTEND_DIR

    return Path(FRONTEND_DIR) / "companion-catalogue.json"


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
