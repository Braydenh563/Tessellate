"""OAuth 2.1 for a remote MCP client such as claude.ai (L-world-class-560, B52).

The MCP authorization spec asks a server for three things, and this is all of
them, on the app's own port, with nothing ever called out to:

- **Metadata** (RFC 9728 and RFC 8414): where to register, authorize and
  trade a code for a token (`api/routes_mcp_oauth.py` serves it).
- **Dynamic client registration** (RFC 7591): a client names itself and its
  redirect addresses and gets a `client_id`. Public clients only (no secret):
  PKCE is what binds the code to the client that asked for it.
- **The authorization code flow with PKCE (S256 only)**: the person's browser
  opens the authorize page, which waits; **the grant is approved on this
  computer**, in Settings, Tools it can use, where the person picks the scope
  and whether it may change notes, matching the short code both screens show.
  Approval makes an ordinary tool server token row (`core/mcp_clients.py`,
  `kind: "oauth"`), so the grant is listed, scoped, counted and revoked like a
  hand-made link. The code is single use and good for five minutes; the
  refresh token rotates on every use.

Pending requests and codes live in memory: a restart drops a half-finished
sign-in, which the client simply starts again. Only hashes of tokens are
stored; a code carries the new token for at most `CODE_SECONDS` in memory.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from urllib.parse import urlsplit

from tessellate.core import deps, mcp_clients
from tessellate.core.security import LOOPBACK_HOSTS

PREF = "mcp_oauth_clients"
SCOPES = ("notes:read", "notes:write")
MAX_REGISTERED = 50
MAX_PENDING = 20
REQUEST_SECONDS = 600.0
CODE_SECONDS = 300.0
REFRESH_PREFIX = "tsl_mcr_"

_lock = threading.Lock()
#: Sign-ins waiting for the person, by request id, and issued codes, by hash.
_pending: dict[str, dict] = {}
_codes: dict[str, dict] = {}


class OAuthError(Exception):
    """An RFC 6749 error: `code` is the `error` field, `why` its description."""

    def __init__(self, code: str, why: str) -> None:
        super().__init__(why)
        self.code = code
        self.why = why


def _now() -> float:
    return time.time()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redirect_ok(uri: str) -> bool:
    """https anywhere, or http on this computer only (OAuth 2.1), no fragment."""
    try:
        parts = urlsplit(str(uri))
    except ValueError:
        return False
    if parts.fragment or not parts.hostname:
        return False
    return parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS)


def _registered() -> list[dict]:
    rows = deps.get_config().get_preference(PREF, [])
    return [dict(row) for row in rows if isinstance(row, dict) and row.get("client_id")] if isinstance(rows, list) else []


def client(client_id: str) -> dict | None:
    return next((row for row in _registered() if hmac.compare_digest(str(row["client_id"]), str(client_id or ""))), None)


def _redirects(body: dict) -> list[str]:
    uris = body.get("redirect_uris") if isinstance(body, dict) else None
    if not isinstance(uris, list) or not 1 <= len(uris) <= 5:
        uris = None
    if uris is None or not all(isinstance(u, str) and redirect_ok(u) for u in uris):
        raise OAuthError("invalid_redirect_uri", "Give one to five redirect addresses, each https, or http on this computer.")
    if (body.get("token_endpoint_auth_method") or "none") != "none":
        raise OAuthError("invalid_client_metadata", "Only public clients are served: token_endpoint_auth_method must be none.")
    return uris


def register(body: dict) -> dict:
    """RFC 7591: a public client and its redirect addresses."""
    uris = _redirects(body)
    row = {
        "client_id": "tsl_oc_" + secrets.token_urlsafe(16),
        "client_name": mcp_clients.clean_name(body.get("client_name") or "") or urlsplit(uris[0]).hostname or "An app",
        "redirect_uris": [u[:400] for u in uris],
        "client_id_issued_at": int(_now()),
    }
    with _lock:
        rows = _registered()
        granted = {r.get("oauth_client") for r in mcp_clients._rows()}
        while len(rows) >= MAX_REGISTERED:
            #: The oldest registration with no live grant makes room; if every
            #: one holds a grant, the oldest goes anyway (its grant keeps working).
            spare = next((r for r in rows if r["client_id"] not in granted), rows[0])
            rows.remove(spare)
        deps.get_config().set_preference(PREF, [*rows, row])
    return {
        **row,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


def _sweep() -> None:
    now = _now()
    for store in (_pending, _codes):
        for key in [k for k, v in store.items() if v["expires"] <= now]:
            store.pop(key, None)


def begin(params: dict) -> dict:
    """Check an authorize request and park it for the person; its id."""
    found = client(params.get("client_id", ""))
    redirect = str(params.get("redirect_uri") or "")
    if found is None:
        raise OAuthError("invalid_client", "That app is not registered here. Register it again.")
    if redirect not in found["redirect_uris"]:
        raise OAuthError("invalid_request", "That redirect address is not one the app registered.")
    if params.get("response_type") != "code":
        raise OAuthError("unsupported_response_type", "Only the code flow is served.")
    challenge = str(params.get("code_challenge") or "")
    if params.get("code_challenge_method") != "S256" or not 43 <= len(challenge) <= 128:
        raise OAuthError("invalid_request", "PKCE with S256 is required.")
    asked = str(params.get("scope") or "").split()
    if any(word not in SCOPES for word in asked):
        raise OAuthError("invalid_scope", "The scopes served are notes:read and notes:write.")
    with _lock:
        _sweep()
        if len(_pending) >= MAX_PENDING:
            raise OAuthError("temporarily_unavailable", "Too many sign-ins are waiting. Approve or deny one first.")
        request_id = secrets.token_urlsafe(24)
        _pending[request_id] = {
            "id": request_id,
            #: The person matches this on both screens before approving.
            "code": "-".join(secrets.token_hex(2).upper() for _ in range(2)),
            "client_id": found["client_id"],
            "client_name": found["client_name"],
            "redirect_uri": redirect,
            "state": str(params.get("state") or "")[:500],
            "challenge": challenge,
            "asks_writes": not asked or "notes:write" in asked,
            "status": "waiting",
            "expires": _now() + REQUEST_SECONDS,
        }
    return _pending[request_id]


def pending(request_id: str) -> dict | None:
    with _lock:
        _sweep()
        return _pending.get(str(request_id or ""))


def waiting() -> list[dict]:
    """Sign-ins Settings shows, oldest first: never the PKCE challenge or state."""
    with _lock:
        _sweep()
        rows = [row for row in _pending.values() if row["status"] == "waiting"]
    return [
        {
            "id": row["id"],
            "code": row["code"],
            "client_name": row["client_name"],
            "redirect_host": urlsplit(row["redirect_uri"]).hostname or "",
            "asks_writes": row["asks_writes"],
            "expires_at": row["expires"],
        }
        for row in rows
    ]


def approve(request_id: str, *, writes: bool, scope: dict | None) -> dict | None:
    """The person said yes: a token row for the grant, and a code for the client."""
    with _lock:
        _sweep()
        row = _pending.get(str(request_id or ""))
        if row is None or row["status"] != "waiting":
            return None
        row["status"] = "busy"
    try:
        grant, token = mcp_clients.create(
            row["client_name"], writes=bool(writes) and row["asks_writes"], scope=scope,
            extra={"kind": "oauth", "oauth_client": row["client_id"]},
        )
    except mcp_clients.TooMany:
        row["status"] = "waiting"
        raise
    refresh = REFRESH_PREFIX + secrets.token_urlsafe(32)
    mcp_clients.set_refresh(grant["id"], _hash(refresh))
    code = secrets.token_urlsafe(32)
    with _lock:
        _codes[_hash(code)] = {
            "client_id": row["client_id"], "redirect_uri": row["redirect_uri"], "challenge": row["challenge"],
            "token": token, "refresh": refresh, "writes": grant["writes"], "expires": _now() + CODE_SECONDS,
        }
        row.update(status="approved", auth_code=code)
    return grant


def deny(request_id: str) -> bool:
    with _lock:
        row = _pending.get(str(request_id or ""))
        if row is None or row["status"] != "waiting":
            return False
        row["status"] = "denied"
    return True


def finish(request_id: str) -> dict | None:
    """What the waiting page does next, once: the row, popped when it is decided."""
    with _lock:
        _sweep()
        row = _pending.get(str(request_id or ""))
        if row is not None and row["status"] in ("approved", "denied"):
            _pending.pop(row["id"], None)
        return row


def _scope_words(writes: bool) -> str:
    return " ".join(SCOPES if writes else SCOPES[:1])


def _verifier_matches(verifier: str, challenge: str) -> bool:
    if not 43 <= len(verifier) <= 128:
        return False
    digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii", "replace")).digest()).rstrip(b"=").decode()
    return hmac.compare_digest(digest, challenge)


def _tokens(token: str, refresh: str, writes: bool) -> dict:
    return {"access_token": token, "token_type": "Bearer", "refresh_token": refresh, "scope": _scope_words(writes)}


def _by_code(form: dict) -> dict:
    with _lock:
        _sweep()
        entry = _codes.pop(_hash(str(form.get("code") or "")), None)  # single use, right or wrong
    if entry is None:
        raise OAuthError("invalid_grant", "That code is wrong, used or expired.")
    same_client = hmac.compare_digest(entry["client_id"], str(form.get("client_id") or ""))
    same_redirect = entry["redirect_uri"] == str(form.get("redirect_uri") or "")
    if not (same_client and same_redirect and _verifier_matches(str(form.get("code_verifier") or ""), entry["challenge"])):
        raise OAuthError("invalid_grant", "That code is wrong, used or expired.")
    return _tokens(entry["token"], entry["refresh"], entry["writes"])


def _by_refresh(form: dict) -> dict:
    given = str(form.get("refresh_token") or "")
    row = mcp_clients.match_refresh(_hash(given)) if given.startswith(REFRESH_PREFIX) else None
    if row is None or not hmac.compare_digest(str(row.get("oauth_client") or ""), str(form.get("client_id") or "")):
        raise OAuthError("invalid_grant", "That refresh token is wrong, used or revoked.")
    refresh = REFRESH_PREFIX + secrets.token_urlsafe(32)
    token = mcp_clients.rotate(row["id"], _hash(refresh))
    if token is None:
        raise OAuthError("invalid_grant", "That grant was revoked.")
    return _tokens(token, refresh, bool(row.get("writes")))


def exchange(form: dict) -> dict:
    """The token endpoint: a code (with its PKCE verifier) or a refresh token."""
    grant = {"authorization_code": _by_code, "refresh_token": _by_refresh}.get(str(form.get("grant_type") or ""))
    if grant is None:
        raise OAuthError("unsupported_grant_type", "The grants served are authorization_code and refresh_token.")
    return grant(form)


def reset() -> None:
    """Forget every waiting sign-in and code (tests, and a lock of the app)."""
    with _lock:
        _pending.clear()
        _codes.clear()
