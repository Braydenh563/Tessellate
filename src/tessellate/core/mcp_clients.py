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

from tessellate.core import deps, mcp_scope

PREF = "mcp_clients"
#: Every token starts with this, so a pasted one is recognisable (and a secret
#: scanner can find one that ends up somewhere it should not).
TOKEN_PREFIX = "tsl_mcp_"
MAX_CLIENTS = 20
MAX_NAME = 60
#: A revoked token stops at once but its row is kept this long, so the Undo on
#: Revoke (and on Make a link) can bring the same token back; then it is gone.
RESTORE_WINDOW = 3600.0

#: Read and written from request threads at once; one lock keeps a call's
#: count and a revoke from overwriting each other's save.
_lock = threading.Lock()


def _now() -> float:
    return time.time()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _all_rows() -> list[dict]:
    """Every stored row, revoked ones still inside the restore window included."""
    rows = deps.get_config().get_preference(PREF, [])
    rows = [dict(row) for row in rows if isinstance(row, dict) and row.get("id") and row.get("hash")] if isinstance(rows, list) else []
    cutoff = _now() - RESTORE_WINDOW
    return [row for row in rows if not row.get("revoked_at") or float(row["revoked_at"]) > cutoff]


def _rows() -> list[dict]:
    """The live rows: the only ones a token can match or Settings lists."""
    return [row for row in _all_rows() if not row.get("revoked_at")]


def _save(rows: list[dict]) -> None:
    deps.get_config().set_preference(PREF, rows)


def public(row: dict) -> dict:
    """A client as Settings shows it: never the hash."""
    return {
        "id": row["id"],
        "name": row.get("name", ""),
        "writes": bool(row.get("writes")),
        "scope": mcp_scope.clean(row.get("scope")),
        "kind": row.get("kind") or "token",
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


def create(name: str, *, writes: bool, scope: dict | None = None, extra: dict | None = None) -> tuple[dict, str]:
    """A new client and its token, which is never stored or shown again.
    `scope` limits the notes it reaches (core/mcp_scope.py); `extra` is the
    OAuth grant's own fields (core/mcp_oauth.py)."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = {
        **(extra or {}),
        "id": secrets.token_hex(6),
        "name": clean_name(name),
        "hash": _hash(token),
        "writes": bool(writes),
        "scope": mcp_scope.clean(scope),
        "created_at": _now(),
        "last_used": None,
        "calls": 0,
    }
    with _lock:
        rows = _all_rows()
        if sum(1 for kept in rows if not kept.get("revoked_at")) >= MAX_CLIENTS:
            raise TooMany
        _save([*rows, row])
    return public(row), token


def revoke(client_id: str) -> bool:
    """The token stops matching now; its row waits `RESTORE_WINDOW` for an Undo."""
    with _lock:
        rows = _all_rows()
        hit = [row for row in rows if row["id"] == client_id and not row.get("revoked_at")]
        if not hit:
            return False
        hit[0]["revoked_at"] = _now()
        _save(rows)
    return True


def restore(client_id: str) -> bool:
    """Undo a revoke inside the window: the same token works again."""
    with _lock:
        rows = _all_rows()
        hit = [row for row in rows if row["id"] == client_id and row.get("revoked_at")]
        if not hit or sum(1 for row in rows if not row.get("revoked_at")) >= MAX_CLIENTS:
            return False
        hit[0].pop("revoked_at", None)
        _save(rows)
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
        rows = _all_rows()
        for row in rows:
            if row["id"] == client_id and not row.get("revoked_at"):
                row["calls"] = int(row.get("calls") or 0) + 1
                row["last_used"] = _now()
        _save(rows)


def set_refresh(client_id: str, refresh_hash: str) -> None:
    """An OAuth grant's refresh token (core/mcp_oauth.py), kept as its hash."""
    with _lock:
        rows = _all_rows()
        for row in rows:
            if row["id"] == client_id:
                row["refresh_hash"] = refresh_hash
        _save(rows)


def match_refresh(offered_hash: str) -> dict | None:
    """The live grant whose refresh token hashes to `offered_hash`. Every row is compared."""
    found = None
    for row in _rows():
        if row.get("refresh_hash") and hmac.compare_digest(offered_hash, str(row["refresh_hash"])):
            found = row
    return found


def rotate(client_id: str, refresh_hash: str) -> str | None:
    """A new access token and refresh hash for a live grant; the old pair stops at once."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    with _lock:
        rows = _all_rows()
        hit = [row for row in rows if row["id"] == client_id and not row.get("revoked_at")]
        if not hit:
            return None
        hit[0].update(hash=_hash(token), refresh_hash=refresh_hash)
        _save(rows)
    return token
