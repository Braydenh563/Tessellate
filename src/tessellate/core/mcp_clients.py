"""Outside clients of the tool server over HTTP, one token each (INBOX 1860).

A token is made in Settings, Tools it can use, and shown once: only its
SHA-256 is kept, in `preferences.json` under `mcp_clients`, beside the name it
was given, whether it may change notes, when it was made and last used, and
how many calls it made. A hash of 32 random bytes cannot be turned back into
the token, so the file never holds anything that opens the notebook; the
stdio server's single token (Q22) stays a secret setting as before.

`match` hashes what was offered and compares it with every stored hash with
`hmac.compare_digest`, never stopping at the first hit, so how long a refusal
takes says nothing about which client, or how much of a token, was right.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

from tessellate.core import deps

PREF = "mcp_clients"
#: Every token starts with this, so a pasted one is recognisable (and a secret
#: scanner can find one that ends up somewhere it should not).
TOKEN_PREFIX = "tsl_mcp_"
MAX_CLIENTS = 20
MAX_NAME = 60

#: Read and written from request threads at once; one lock keeps a call's
#: count and a revoke from overwriting each other's save.
_lock = threading.Lock()


def _now() -> float:
    return time.time()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _rows() -> list[dict]:
    rows = deps.get_config().get_preference(PREF, [])
    return [dict(row) for row in rows if isinstance(row, dict) and row.get("id") and row.get("hash")] if isinstance(rows, list) else []


def _save(rows: list[dict]) -> None:
    deps.get_config().set_preference(PREF, rows)


def public(row: dict) -> dict:
    """A client as Settings shows it: never the hash."""
    return {
        "id": row["id"],
        "name": row.get("name", ""),
        "writes": bool(row.get("writes")),
        "created_at": row.get("created_at"),
        "last_used": row.get("last_used"),
        "calls": int(row.get("calls") or 0),
    }


def listing() -> list[dict]:
    return [public(row) for row in _rows()]


def clean_name(name: str) -> str:
    return " ".join(str(name or "").split())[:MAX_NAME]


class TooMany(Exception):
    """Already `MAX_CLIENTS` tokens: revoke one first."""


def create(name: str, *, writes: bool) -> tuple[dict, str]:
    """A new client and its token, which is never stored or shown again."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = {
        "id": secrets.token_hex(6),
        "name": clean_name(name),
        "hash": _hash(token),
        "writes": bool(writes),
        "created_at": _now(),
        "last_used": None,
        "calls": 0,
    }
    with _lock:
        rows = _rows()
        if len(rows) >= MAX_CLIENTS:
            raise TooMany
        _save([*rows, row])
    return public(row), token


def revoke(client_id: str) -> bool:
    with _lock:
        rows = _rows()
        kept = [row for row in rows if row["id"] != client_id]
        if len(kept) == len(rows):
            return False
        _save(kept)
    return True


def match(given: str) -> dict | None:
    """The client whose token `given` is, or None. Every row is compared."""
    if not given or not given.startswith(TOKEN_PREFIX):
        return None
    offered = _hash(given)
    found = None
    for row in _rows():
        if hmac.compare_digest(offered, str(row["hash"])):
            found = row
    return found


def note_use(client_id: str) -> None:
    """One more call on the client's row, and when."""
    with _lock:
        rows = _rows()
        for row in rows:
            if row["id"] == client_id:
                row["calls"] = int(row.get("calls") or 0) + 1
                row["last_used"] = _now()
        _save(rows)
