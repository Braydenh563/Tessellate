"""Single-user unlock.

One password, bcrypt-hashed in the `users` table, and an optional PIN that
unlocks this computer only (`core/pinstore.py`, kept by the OS, never in the
notebook). Unlocking
issues a random token the frontend sends back as X-Auth-Token; tokens
live in memory only, so restarting the app locks it again, and they
expire on their own after a spell unused, see _SESSION_IDLE_TTL.

Before a password has been set there is nothing to protect (the app is
brand new and empty), so the API stays open and the frontend forces the
setup screen first.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import logging
import os
import re
import secrets
import threading
import time
import urllib.parse
from pathlib import Path

import bcrypt
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import (
    crypto,
    desktop_dialog,
    diskspace,
    lanlive,
    lantrust,
    netbind,
    password_reset,
    pinstore,
    reminder_token,
    security,
    vault,
)
from tessellate.core.config import ConfigManager
from tessellate.core.deps import get_config, get_session, register_cache_reset
from tessellate.core.database import Entry, User, Vault
from tessellate.entry import manager
from tessellate.entry.manager import log_action
from tessellate.api.this_computer import REFUSAL, is_another_device, this_computer_only

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory sessions: fine for a single-user local app.
#
# Each token remembers when it was issued and when it was last used, because a
# token that never expires is a second key to the notebook that nobody can take
# back. Restarting the app clears them, which sounds like it covers this, but
# the app this is built for is a desktop notebook that stays open for weeks, so
# "until the next restart" can be a very long time. Two clocks, doing different
# jobs:
#
#   idle: you walked away. The notebook locks itself like a phone does.
#   max age: you did not walk away, but a token issued a fortnight ago should
#             not still be valid; this is the ceiling that a token leaked from
#             a proxy log or a synced browser profile eventually hits.
#
# The session token is never a cookie: it travels as an X-Auth-Token header the
# frontend sets explicitly, so a browser never attaches it to a cross-site
# request on its own. That is a stronger position than a SameSite cookie
# rather than a gap in one. The one cookie this app sets is the media ticket
# below, which opens pictures and files and nothing else.
_SESSION_IDLE_TTL = 12 * 60 * 60  # fallback default; overridden by the
# session_idle_ttl_minutes preference (Settings → Account) once one is set
_SESSION_MAX_AGE = 7 * 24 * 60 * 60  # this old → expired, however busy

# token -> [issued_at, last_used_at]
_active_tokens: dict[str, list[float]] = {}

# **The media ticket** (WORLD_CLASS_PLAN §12, S1). A declarative load (`<img
# src>`, an `<iframe>`, a CSS background) cannot attach the X-Auth-Token
# header, so `mediaSrc()` used to append `?token=<session token>` to every
# `/media` and `/files` URL. That put the one credential that opens the whole
# notebook into browser history, uvicorn's access log, and any note a person
# pasted an image address into; on localhost a nuisance, on a LAN a leak.
#
# Now unlocking sets a cookie instead, and three properties do the work:
#
#   HttpOnly: no script on the page can read it, so an injected one cannot
#             lift it the way it could read a URL.
#   SameSite=Strict: another site cannot make the browser send it, so an
#             `<img>` on a page elsewhere pointing here loads nothing.
#   Path=/media and Path=/files: the browser sends it to those two prefixes
#             only, and it holds a *ticket*, not the session token, so even a
#             copy of it opens pictures and files and never the API.
#
# A ticket lives exactly as long as its session: it names one, and the gate
# checks that session is still live on every use.
MEDIA_COOKIE = "memorymap_media"
# `/mermaid-frame` too: the diagram frame is a page load, which sends no header.
MEDIA_COOKIE_PATHS = ("/media", "/files", "/mermaid-frame")
# ticket -> the session token it was issued for
_media_tickets: dict[str, str] = {}
register_cache_reset(_media_tickets.clear)

# The desktop window's "Open in a new tab" hands the link to the system
# browser, a different cookie jar with no media cookie (the owner,
# 2026-10-27: the tab said "The app is locked"). A one-file link carries a
# `once` ticket instead: it opens that one path only, for two minutes, while
# its session lives; never the session token, never the API. Reusable inside
# its life because a PDF viewer asks for ranges more than once.
MEDIA_LINK_SECONDS = 120
# ticket -> (decoded path, expiry, session token)
_media_links: dict[str, tuple[str, float, str]] = {}
register_cache_reset(_media_links.clear)
_MEDIA_LINK_PATH = re.compile(r"/(?:media|files)/[A-Za-z0-9._~%/-]+")
# Module state, not app state, so `deps.reset_app_state()` (the thing every
# test's `app_state` fixture calls) threw the database away and kept the
# tokens. Any test that ran `/auth/setup` before `test_account.py` in the same
# process left it counting four active sessions instead of one; the suite only
# stayed green because of alphabetical order. Registered as a cache reset so
# the store is dropped with everything else.
register_cache_reset(_active_tokens.clear)


class VaultScope:
    """Serve each request as the session its X-Auth-Token names.

    Pure ASGI rather than `BaseHTTPMiddleware`, so the context variable is set
    in the request's own task and everything under it (the threadpool a sync
    route runs in, a streaming body's iterator) reads the same session. What
    it grants is decided in `core/vault.py`; this only says who is asking.
    A request with no header is served as a session with no token, which is
    never granted anything.
    """

    def __init__(self, app) -> None:  # noqa: ANN001  # an ASGI app
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001  # ASGI
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        token = None
        for name, value in scope.get("headers") or ():
            if name == b"x-auth-token":
                token = value.decode("latin-1")
                break
        with vault.request_scope(token):
            await self.app(scope, receive, send)


def _sweep_expired(idle_ttl: int) -> None:
    """Drop dead tokens, and forget the data key once none are left.

    Closing the vault matters as much as dropping the token: expiry that left
    private notes decrypted in memory would be a lock that only locks the door
    it is written on.
    """
    now = time.time()
    dead = [
        token
        # A snapshot, and pop: requests run in the threadpool, and an unlock
        # on one device mid-sweep on another raised "dictionary changed size
        # during iteration" or a KeyError (audit 1028 K2).
        for token, (issued, seen) in list(_active_tokens.items())
        if now - seen > idle_ttl or now - issued > _SESSION_MAX_AGE
    ]
    for token in dead:
        _active_tokens.pop(token, None)
    if dead:
        _forget_dead_tickets()
        # The key goes with the last session that gave the password, even
        # while a session without it is still live (tests/test_vault_sessions).
        vault.revoke(dead)
    if dead and not _active_tokens:
        vault.close()


def _forget_dead_tickets() -> None:
    """Drop every media ticket whose session is gone."""
    for ticket in [t for t, token in _media_tickets.items() if token not in _active_tokens]:
        del _media_tickets[ticket]


def _cookie_secure(request: Request) -> bool:
    """Whether the media cookie may carry `Secure` on this request.

    Always over https. Over plain http only on a loopback host, where
    Chromium (the desktop window's WebView2 included) and Firefox treat
    the origin as trustworthy and still store a `Secure` cookie; anywhere
    else on http a `Secure` cookie is silently dropped by the browser and
    every picture in the notebook would stop loading."""
    if request.url.scheme == "https":
        return True
    return (request.url.hostname or "") in _LOOPBACK_HOSTS


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# **Optional sign-in** (INBOX 426 aa, the owner's brother: "some people might
# not care about it and find it annoying"). One switch in Settings, Account
# and security: "Ask for a password when the app opens", on by default. Off,
# this computer is handed a session without the password; nothing else is.
#
# Kept in preferences.json but deliberately **not** declared on
# `PreferencesBody` (routes_settings.py): `PUT /preferences` writes only the
# fields it declares, so the one way to turn this off is the route below that
# asks for the current password. tests/test_optional_sign_in.py holds that.
PASSWORD_ON_OPEN_KEY = "ask_password_on_open"

#: Headers a proxy or tunnel adds. Their presence on a loopback connection
#: means the person asking is somewhere else, whatever address they claim, so
#: a request carrying any of them is never given a password-free session.
#: They are only ever *looked for*, never believed: the address used is
#: `request.client.host`, the one uvicorn resolved for the connection.
_FORWARDING_HEADERS = (
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-real-ip",
)


def password_on_open(config: ConfigManager) -> bool:
    """Whether the app asks for the password when it opens (default: yes)."""
    return config.get_preference(PASSWORD_ON_OPEN_KEY, True) is not False


def _is_loopback_address(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    return bool(address.is_loopback or (mapped is not None and mapped.is_loopback))


def _from_this_computer(request: Request) -> bool:
    """Is this request from a person at this machine's own keyboard?

    Three conditions, each closing a different door:

    - the connection's own address is loopback (`request.client.host`, which
      is what uvicorn resolved; a LAN device is never let in without the
      password, whatever it sends);
    - no forwarding header at all, because a tunnel or reverse proxy on this
      machine connects from 127.0.0.1 on somebody else's behalf;
    - the Host the browser named is a loopback name. A DNS-rebinding page
      (evil.example re-pointed at 127.0.0.1) reaches this server from
      loopback and is same-origin with itself, so the Origin check in
      core/security.py passes it; the Host it sends is still its own name.
    """
    client = request.client.host if request.client else ""
    if not _is_loopback_address(client or ""):
        return False
    if any(name in request.headers for name in _FORWARDING_HEADERS):
        return False
    hostname = request.url.hostname or ""
    return hostname in _LOOPBACK_HOSTS or (bool(hostname) and hostname == netbind.local_name())


def _auto_session_allowed(request: Request, session: Session, config: ConfigManager) -> bool:
    if _get_user(session) is None:
        return False  # setup still makes a password: the vault needs one
    if password_on_open(config):
        return False
    return _from_this_computer(request)


def _grant_media(request: Request, response: Response, token: str) -> None:
    """Set the media cookie for this session (see MEDIA_COOKIE above)."""
    # One live ticket per session. A browser holds one cookie per path, so a
    # session's earlier ticket is already gone from the jar it was set in;
    # keeping it here would only let the table grow by one per reload (the
    # boot path asks again every time) until the session ends.
    for stale in [t for t, owner in _media_tickets.items() if owner == token]:
        del _media_tickets[stale]
    ticket = secrets.token_urlsafe(32)
    _media_tickets[ticket] = token
    for path in MEDIA_COOKIE_PATHS:
        response.set_cookie(
            MEDIA_COOKIE,
            ticket,
            max_age=_SESSION_MAX_AGE,
            path=path,
            httponly=True,
            secure=_cookie_secure(request),
            samesite="strict",
        )


def _revoke_media(request: Request, response: Response) -> None:
    """Tell the browser to drop the media cookie on both paths."""
    for path in MEDIA_COOKIE_PATHS:
        response.delete_cookie(
            MEDIA_COOKIE,
            path=path,
            httponly=True,
            secure=_cookie_secure(request),
            samesite="strict",
        )


def _token_valid(token: str | None, idle_ttl: int) -> bool:
    """Is this token live? Using it also keeps it alive."""
    _sweep_expired(idle_ttl)
    entry = _active_tokens.get(token) if token else None
    if entry is None:
        return False
    entry[1] = time.time()
    return True

# Brute-force throttle for unlock attempts. The app binds 127.0.0.1, but a
# server log showed a public client address arriving through a proxy header,
# people do put this behind tunnels to reach it from a phone. bcrypt makes
# each guess slow; nothing made *many* guesses slow, and the password floor
# is four characters, which is PIN territory. Wrong guesses beyond the free
# allowance earn an exponentially growing wait; a right password inside the
# wait still waits.
#
# **Two layers** (WORLD_CLASS_PLAN §12, S2). Until 2026-09-24 this was one
# global bucket, on the reasoning that there is a single user to protect and
# per-address buckets are what a botnet has plenty of. True, and it had the
# cost the review named: five wrong tries from *anyone* locked the owner out
# for up to five minutes, which on localhost is only ever the owner and on a
# LAN is a denial of service any device can run. So each client address now
# earns its own waits at the old allowance, and the global list stays as the
# backstop at a far larger one: a guesser at one address is slowed after
# five, many addresses guessing together are slowed after fifty between
# them, and the owner at their own address is slowed by neither until then.
# On loopback every request is 127.0.0.1, so the local case is unchanged.
_FAILURE_ALLOWANCE = 5  # free tries per client before the waits start
_GLOBAL_FAILURE_ALLOWANCE = 50  # free tries across every client together
_FAILURE_WINDOW = 15 * 60  # forgiven this long after the last failure
_WAIT_CEILING = 300  # the wait stops growing at five minutes
#: Clients remembered at once. A guesser rotating addresses must not be able
#: to grow this table without end; past the cap the quietest one is dropped,
#: and the global list still counts every guess it made.
_MAX_TRACKED_CLIENTS = 1024
_failed_unlocks: list[float] = []  # every failure, from anyone: the backstop
_failed_by_client: dict[str, list[float]] = {}


#: Guesses let through and not yet answered, per client (audit 1028 K3).
#: The throttle checked before bcrypt and counted after, so forty guesses
#: sent at once all passed a check that allows five. An attempt in flight
#: counts as a failure until it is answered; one never answered (a route
#: that raised for another reason) is dropped after a minute.
_pending_unlocks: dict[str, list[float]] = {}
_PENDING_TTL = 60.0
_throttle_lock = threading.RLock()


def _clear_unlock_failures() -> None:
    _failed_unlocks.clear()
    _failed_by_client.clear()
    _pending_unlocks.clear()


def _answered(client: str) -> None:
    """One in-flight attempt from `client` (already bucketed) has an answer."""
    pending = _pending_unlocks.get(client)
    if pending:
        pending.pop(0)
        if not pending:
            _pending_unlocks.pop(client, None)


register_cache_reset(_clear_unlock_failures)


def _client_key(request: Request | None) -> str:
    """Who is guessing: the address uvicorn resolved for this connection.

    `request.client.host` already honours `--forwarded-allow-ips`, so a
    proxy the operator trusts is seen through and one they do not is not;
    nothing here reads a forwarding header itself, which is what would let a
    guesser name a fresh address per request.
    """
    if request is None or request.client is None:
        return "unknown"
    return request.client.host or "unknown"


def _bucket(client: str) -> str:
    """The throttle's key for a client address (lansec-1025). An IPv6 device
    chooses its own address inside the network's /64 (privacy addresses do
    it hourly), so a guesser keyed by the full address earned five free
    tries per address it made up: it is keyed by the /64. An IPv4 address
    that arrived as `::ffff:a.b.c.d` is the IPv4 address."""
    try:
        address = ipaddress.ip_address(client.split("%", 1)[0])
    except ValueError:
        return client
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        return str(mapped)
    if address.version == 6 and not address.is_loopback:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def _wait_left(failures: list[float], allowance: int, now: float) -> float:
    """Seconds of wait this list of failures has earned, 0 when none."""
    if failures and now - failures[-1] > _FAILURE_WINDOW:
        failures.clear()  # long quiet: forgiven
    over = len(failures) - allowance
    if over < 0:
        return 0.0
    wait = min(2 ** over, _WAIT_CEILING)
    return wait - (now - failures[-1])


def _drop_stale_pending(now: float) -> None:
    """Forget unlock attempts older than the pending window. Caller holds the lock."""
    for key in list(_pending_unlocks):
        kept = [t for t in _pending_unlocks[key] if now - t < _PENDING_TTL]
        if kept:
            _pending_unlocks[key] = kept
        else:
            del _pending_unlocks[key]


def _refuse_if_throttled(client: str = "unknown") -> None:
    """429 while inside the wait a run of wrong passwords has earned."""
    client = _bucket(client)
    with _throttle_lock:
        now = time.time()
        _drop_stale_pending(now)
        own = _failed_by_client.get(client)
        if own is not None:
            _wait_left(own, _FAILURE_ALLOWANCE, now)  # forgets a long-quiet run
        _wait_left(_failed_unlocks, _GLOBAL_FAILURE_ALLOWANCE, now)
        mine = sorted((own or []) + _pending_unlocks.get(client, []))
        everyone = sorted(_failed_unlocks + [t for ts in _pending_unlocks.values() for t in ts])
        remaining = max(
            _wait_left(mine, _FAILURE_ALLOWANCE, now) if mine else 0.0,
            _wait_left(everyone, _GLOBAL_FAILURE_ALLOWANCE, now) if everyone else 0.0,
        )
        if own is not None and not own:
            _failed_by_client.pop(client, None)
        if remaining <= 0:
            _pending_unlocks.setdefault(client, []).append(now)
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many wrong passwords. Try again in {int(remaining) + 1} "
                f"second{'' if int(remaining) == 0 else 's'}."
            ),
        )


def _unlock_failed(client: str = "unknown") -> None:
    client = _bucket(client)
    with _throttle_lock:
        _answered(client)
        _record_failure(client)


def _record_failure(client: str) -> None:
    now = time.time()
    _failed_unlocks.append(now)
    _failed_by_client.setdefault(client, []).append(now)
    if len(_failed_by_client) > _MAX_TRACKED_CLIENTS:
        quietest = min(_failed_by_client, key=lambda key: _failed_by_client[key][-1])
        del _failed_by_client[quietest]


def _unlock_succeeded(client: str = "unknown") -> None:
    client = _bucket(client)
    with _throttle_lock:
        _answered(client)
    # The global list too: whoever got the password right is the owner, and
    # a backstop that outlived the owner's own unlock would be the lockout
    # this change exists to remove. Other clients' own buckets are kept.
    _failed_by_client.pop(client, None)
    _failed_unlocks.clear()


#: The longest password the routes accept (SEC-06/SEC-09, audit 2026-10-05).
#: Far past any passphrase a person types, and short enough that a request
#: cannot make the server hash a megabyte before it has said who it is.
MAX_PASSWORD_CHARS = 1024

#: bcrypt reads at most 72 bytes, and bcrypt 5 raises past that instead of
#: truncating: a long passphrase (or 25 emoji) was a 500 at setup, unlock
#: and change (SEC-09). A longer password is pre-hashed to a fixed 54 bytes
#: first. No marker is stored: which form a hash took follows from the
#: candidate's own length, and every hash made before this change was of a
#: password of 72 bytes or fewer (bcrypt 5 refused anything longer), so
#: those verify exactly as before.
_BCRYPT_MAX_BYTES = 72


def _bcrypt_input(password: str) -> bytes:
    raw = password.encode()
    if len(raw) <= _BCRYPT_MAX_BYTES:
        return raw
    # PBKDF2 rather than a bare digest: the input is a password, and a fast
    # hash in front of bcrypt reads to a scanner (CodeQL, py/weak-sensitive-
    # data-hashing) as the password's only hash. A fixed salt is right here:
    # this only fits the input to bcrypt's 72 bytes, bcrypt salts the result.
    # The salt keeps the app's old name for good, through the rename to
    # Tessellate: a new one would fail every stored long password.
    return b"mm-pbkdf2:" + base64.b64encode(hashlib.pbkdf2_hmac("sha256", raw, b"memorymap-bcrypt-input", 10_000))


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt()).decode()


def _password_matches(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_bcrypt_input(password), password_hash.encode())
    except ValueError:
        return False  # a malformed stored hash opens nothing


#: **The floor for a new password** (SEC-17, audit 2026-10-05). The bcrypt
#: hash and the scrypt-wrapped key both live in the database file, so a
#: stolen copy or backup is guessed offline at whatever speed the thief's
#: machine has, and the old four-character floor (a PIN) falls in minutes.
#: Eight for every new password, at setup and change; one set before this
#: keeps working, so the floor never locks anyone out of their own notes.
NEW_PASSWORD_MIN_CHARS = 8

_COMMON_PASSWORDS = frozenset({
    "password", "password1", "password123", "passw0rd", "12345678", "123456789",
    "1234567890", "87654321", "11111111", "00000000", "qwertyuiop", "qwerty123",
    "iloveyou", "letmein1", "welcome1", "sunshine", "princess", "football",
    "baseball", "dragon12", "monkey12", "trustno1", "abc12345", "admin123",
    "memorymap", "notebook", "changeme",
})
_RUNS = ("abcdefghijklmnopqrstuvwxyz", "01234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm")


def _new_password_problem(password: str) -> str | None:
    """Why a new password is refused, or None."""
    if len(password) < NEW_PASSWORD_MIN_CHARS:
        return f"Use at least {NEW_PASSWORD_MIN_CHARS} characters for a new password."
    return None


def password_warning(password: str) -> str | None:
    """A sentence when an allowed password is still easy to guess, else None.

    Deliberately small: common choices, one character repeated, a run along
    the alphabet, the digits or a keyboard row, and short ones made of a
    single kind of character. Not a rule, a warning: the person decides.
    """
    lowered = password.lower()
    kinds = sum(
        (
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        )
    )
    weak = (
        lowered in _COMMON_PASSWORDS
        or len(set(lowered)) <= 2
        or any(lowered in run or lowered in run[::-1] for run in _RUNS)
        or (len(password) < 12 and kinds <= 1)
    )
    if not weak:
        return None
    return (
        "This password is easy to guess. Someone with a copy of your notebook "
        "file could try guesses offline, so a longer one, or three or four "
        "unrelated words, keeps private notes much safer."
    )


class PasswordBody(BaseModel):
    password: str = Field(
        min_length=4,
        max_length=MAX_PASSWORD_CHARS,
        description="Your password, or on this computer only, the PIN set up here",
    )


def _get_user(session: Session) -> User | None:
    return session.scalar(select(User))


#: **The gate's "is there a password" answer, remembered for a few seconds,
#: and only when it is yes** (INBOX 472). `require_unlock` runs on every data
#: request and asked the database each time: 0.4 ms of a 2.5 ms request,
#: measured in process (scratchpad/asgi_bench.py), and a boot makes about
#: forty. Only the positive answer is kept, so the cache can only ever make the
#: gate *ask* for a token, never wave a request through: a notebook that gains
#: a password (setup, a restored backup) is gated from the very next request,
#: and one that loses it (the command-line reset, run while the server is up)
#: asks for a token for at most `_OWNER_TTL` seconds longer. Keyed per engine,
#: since each test app has its own database.
_OWNER_TTL = 10.0
_owner_seen: dict[int, float] = {}
register_cache_reset(_owner_seen.clear)


def _password_set(session: Session) -> bool:
    key = id(session.get_bind())
    seen = _owner_seen.get(key)
    now = time.monotonic()
    if seen is not None and now - seen < _OWNER_TTL:
        return True
    if _get_user(session) is None:
        _owner_seen.pop(key, None)
        return False
    _owner_seen[key] = now
    return True


def notebook_open(session: Session, config: ConfigManager) -> bool:
    """Whether a reminder's text may be put on screen without a request: no
    password yet, or a live session (the desktop notifier,
    `core/reminder_notifier.py`). Sweeping does not touch a token's last use,
    so asking never keeps a session alive."""
    if not _password_set(session):
        return True
    _sweep_expired(config.get_preference("session_idle_ttl_minutes", _SESSION_IDLE_TTL // 60) * 60)
    return bool(_active_tokens)


def _no_password_yet(request: Request, session: Session) -> bool:
    """No password, so nothing to check: true only at this computer.

    The network port binds only once a password exists, but it stays open
    until the next launch, and "I don't have it" (`/auth/reset`) or a restored
    backup with no password could leave a notebook with none behind a live
    LAN listener: every route answered any device then (measured: `/entries`
    200 and a `/auth/setup` that took the notebook, from a 192.168 client).
    A container's published port (Brief 40) is the exception: no window
    there to set up from.
    """
    if _password_set(session):
        return False
    if is_another_device(request) and not netbind.explicit_bind():
        raise HTTPException(status_code=401, detail=NO_PASSWORD_ELSEWHERE)
    return True


#: What another device is told while this notebook has no password.
NO_PASSWORD_ELSEWHERE = "Set a password on the computer Tessellate runs on first."


def require_unlock(
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
) -> None:
    """Dependency that gates every data route once a password exists."""
    if _no_password_yet(request, session):
        return  # setup not done yet, nothing to protect
    idle_ttl = config.get_preference("session_idle_ttl_minutes", _SESSION_IDLE_TTL // 60) * 60
    if not _token_valid(x_auth_token, idle_ttl):
        raise HTTPException(status_code=401, detail="The app is locked. Unlock it first.")


def require_unlock_media(
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
    memorymap_media: str | None = Cookie(default=None),
    once: str | None = Query(default=None),
) -> None:
    """Same gate as `require_unlock`, plus the media cookie (or a one-file
    link, `MEDIA_LINK_SECONDS`).

    For the handful of routes a plain `<img src>` points at directly
    (`/media/{filename}`, `/files/{attachment_id}` and their page and preview
    renders), a declarative resource load never attaches a custom header,
    only `fetch`/`XHR` can, so every such image was a silent 401 on any
    notebook with a password set, which is the normal case. The cookie is
    what such a load carries (see MEDIA_COOKIE); a `fetch` still sends the
    header. **A `?token=` query parameter is no longer read**: it was the
    fallback here until 2026-09-24, and it was the leak S1 describes.
    """
    if _no_password_yet(request, session):
        return
    idle_ttl = config.get_preference("session_idle_ttl_minutes", _SESSION_IDLE_TTL // 60) * 60
    token = x_auth_token or _media_tickets.get(memorymap_media or "")
    if not token and once:
        path, expires, link_token = _media_links.get(once, ("", 0.0, ""))
        if path == request.scope.get("path") and time.time() < expires:
            token = link_token
    if not _token_valid(token, idle_ttl):
        raise HTTPException(status_code=401, detail="The app is locked. Unlock it first.")


def end_every_session() -> int:
    """Sign every session out and forget the data key; the number ended.

    For a change underneath every session at once: a restored backup
    (SEC-07, security audit 2026-10-05) can carry a different wrapped key,
    or a different password, or none, so the key in memory and every token
    issued against the old database stop meaning anything. Left in place,
    the post-rotation key went on encrypting new private notes that the
    restored vault row could never unwrap again.
    """
    ended = len(_active_tokens)
    reminder_token.rotate(get_config().data_dir)
    _active_tokens.clear()
    _media_tickets.clear()
    _owner_seen.clear()
    vault.revoke_all()
    vault.close()
    # The PIN is bound to the vault row being replaced (`pinstore.binding`):
    # it could open nothing now, so it goes rather than lingering as five
    # strikes' worth of guesses at a record that is already dead.
    pinstore.forget(get_config().data_dir)
    return ended


def _issue_token() -> str:
    token = secrets.token_hex(32)
    now = time.time()
    _active_tokens[token] = [now, now]
    return token


@router.get("/status")
def status(
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    # `auto_session` answers for this caller only: whether *this* request
    # would be given a session without a password. A LAN device is told
    # False, which is all it needs to draw the lock screen.
    #
    # `reset_here` (INBOX 663) is also about the caller only: whether this
    # device may use "Forgot your password?" (`_from_this_computer`), so the
    # card can say "do it on the computer the notebook lives on" before
    # anyone types a key. It is deliberately the only reset fact this open
    # route gives: not whether a recovery key exists, not how many private
    # notes there are. The card offers both paths either way, and a wrong or
    # absent key earn the same answer from `/auth/recover`.
    return {
        "setup_required": _get_user(session) is None,
        "auto_session": _auto_session_allowed(request, session, config),
        "reset_here": _from_this_computer(request),
        # Whether this caller may type a PIN: set, and this computer. Any
        # other device is told False whether or not there is one.
        "pin_here": _from_this_computer(request) and pinstore.is_set(config.data_dir),
    }


@router.post("/setup")
def setup(body: PasswordBody, request: Request, response: Response, session: Session = Depends(get_session)) -> dict:
    """First run: create the single user. Refuses to run twice, and to any
    other device (`_no_password_yet`): whoever sets it owns the notebook."""
    if _get_user(session) is not None:
        raise HTTPException(status_code=400, detail="A password is already set.")
    if is_another_device(request) and not netbind.explicit_bind():
        raise HTTPException(status_code=403, detail=NO_PASSWORD_ELSEWHERE)
    problem = _new_password_problem(body.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    password_hash = _hash_password(body.password)
    session.add(User(username="owner", password_hash=password_hash))
    # Create the vault now, while the password is in hand. Deferring it would
    # mean a second prompt later, and a second chance to lose access.
    vault.create(session, body.password)
    log_action(session, "created", "user", detail="password set")
    session.commit()
    token = _issue_token()
    vault.grant(token)
    _grant_media(request, response, token)
    return {"token": token, "warning": password_warning(body.password)}


# --- new devices wait for this computer (INBOX 867, core/lantrust.py) --------------

#: How long one sign-in from a new device waits for Allow before answering.
#: Long enough for the person holding the phone to reach the computer;
#: pressing Unlock again waits once more.
DEVICE_WAIT_SECONDS = 45.0
#: Waiting holds a worker thread, so only this many wait at once; any more
#: are told to press Unlock again.
_device_waits = threading.BoundedSemaphore(4)
#: Which device each LAN session belongs to, so Remove signs it out.
_device_tokens: dict[str, str] = {}
#: Every token handed to another device, whether or not it had a device
#: cookie: switching LAN mode off ends them all (INBOX 900).
_network_tokens: set[str] = set()


def _end_network_sessions() -> int:
    """Sign out every other device now: LAN mode was switched off."""
    ended = [t for t in _network_tokens if t in _active_tokens]
    for token in ended:
        _active_tokens.pop(token, None)
        _device_tokens.pop(token, None)
    if ended:
        vault.revoke(ended)
    _network_tokens.clear()
    _forget_dead_tickets()
    return len(ended)


def _device_cookie(request: Request) -> str:
    raw = request.cookies.get(lantrust.DEVICE_COOKIE, "")
    return raw if 20 <= len(raw) <= 100 and raw.replace("-", "").replace("_", "").isalnum() else ""


def _set_device_cookie(response: Response, raw: str) -> None:
    #: Only the LAN port is https, and only a device on the network has one.
    #: Written only with an id this server minted, never echoed back from a
    #: request (CodeQL: cookie built from user input), so it lasts 400 days
    #: from first issue and an older device is asked about once again.
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,100}", raw or ""):
        return
    response.set_cookie(
        lantrust.DEVICE_COOKIE, raw, max_age=400 * 24 * 3600, path="/auth",
        httponly=True, secure=True, samesite="strict",
    )


def _from_the_network(request: Request) -> bool:
    """A numeric client address off loopback: a phone or another computer.
    A name (the test client's `testclient`) is nothing to judge."""
    host = request.client.host if request.client else ""
    try:
        ipaddress.ip_address((host or "").split("%", 1)[0])
    except ValueError:
        return False
    return not _is_loopback_address(host)


def _device_must_wait(request: Request, config: ConfigManager) -> bool:
    """Loopback never waits, nor a container's published port (Brief 40: no
    window there to answer), nor anyone once "Ask before a new device signs
    in" is off."""
    if not _from_the_network(request) or netbind.explicit_bind():
        return False
    if not lantrust.load(config.data_dir)["ask_new_devices"]:
        return False
    return not lantrust.device_known(config.data_dir, _device_cookie(request))


def _hold_new_device(request: Request, device: str, config: ConfigManager) -> JSONResponse | None:
    """Hold this sign-in until this computer answers; None once allowed."""
    minted = "" if device else secrets.token_urlsafe(32)
    raw = device or minted
    lantrust.hold(raw, lantrust.device_name(request.headers.get("user-agent")), _client_key(request))
    decision = None
    if _device_waits.acquire(blocking=False):
        try:
            decision = lantrust.wait_decision(raw, DEVICE_WAIT_SECONDS)
        finally:
            _device_waits.release()
    if decision == "allowed":
        lantrust.settle(raw)
        request.cookies[lantrust.DEVICE_COOKIE] = raw  # this unlock goes on as that device
        return None
    if decision == "denied":
        lantrust.settle(raw)
        detail = "The computer this notebook is on said no to this device."
    else:
        detail = (
            "This device is new, so the computer this notebook is on has to allow it first. "
            "Choose Allow in the notice there, then press Unlock again."
        )
    refused = JSONResponse(status_code=403, content={"detail": detail, "device_pending": decision is None})
    if minted:
        _set_device_cookie(refused, minted)
    return refused


def _pin_binding(session: Session, user: User) -> bytes | None:
    row = session.scalar(select(Vault))
    if row is None:
        return None
    return pinstore.binding(user.password_hash, bytes(row.kdf_salt), bytes(row.wrapped_dek))


def _unlock_with_pin(
    request: Request, session: Session, user: User, typed: str, config: ConfigManager
) -> bytes | None:
    """The data key a right PIN unwraps, or None after counting the failure.

    Only after the password has already failed, and only from this computer
    (`_from_this_computer`: loopback, no forwarding header, a loopback Host).
    From anywhere else a PIN is just a wrong password and costs no strike,
    so a device on the network can neither use it nor wipe it. A wrong PIN
    is also a wrong guess for the address's waits, like any other.
    """
    client = _client_key(request)
    if not _from_this_computer(request) or not pinstore.valid_pin(typed):
        _unlock_failed(client)
        return None
    bound = _pin_binding(session, user)
    outcome, dek = pinstore.unlock(config.data_dir, typed, bound) if bound else ("none", None)
    if outcome == "ok":
        return dek
    _unlock_failed(client)
    if outcome == "wiped":
        log_action(session, "edited", "user", user.id, "PIN removed after five wrong tries")
        session.commit()
        raise HTTPException(
            status_code=401,
            detail="That PIN was wrong five times, so it has been removed. Use your password.",
        )
    if outcome == "wrong":
        raise HTTPException(status_code=401, detail="That PIN or password is wrong.")
    return None


@router.post("/unlock")
def unlock(
    body: PasswordBody,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    client = _client_key(request)
    _refuse_if_throttled(client)
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    pin_dek = None
    if not _password_matches(body.password, user.password_hash):
        pin_dek = _unlock_with_pin(request, session, user, body.password, config)
        if pin_dek is None:
            raise HTTPException(status_code=401, detail="That password is wrong.")
    _unlock_succeeded(client)
    device = _device_cookie(request)
    if pin_dek is None and _device_must_wait(request, config):
        refused = _hold_new_device(request, device, config)
        if refused is not None:
            return refused
    # Unwrap the data key so private notes are readable for this session.
    if pin_dek is not None:
        vault.set_key(pin_dek)  # bound to this very vault row (`_pin_binding`)
        vault_open = True
    else:
        vault_open = vault.open_with(session, body.password)
    #: **A full disk must not lock you out of your own notebook.** Measured
    #: (INBOX 266, item 6) on a data dir filled to 100%: this route answered
    #: 507 and the app became unopenable, while every read endpoint behind it
    #: was answering 200 perfectly well. Unlocking is a password check and an
    #: in-memory token; the only writes near it are a vault row on the first
    #: unlock after an upgrade and an audit line, and neither is worth the
    #: notebook. Both are committed separately now so a failure costs only
    #: itself, and only an out-of-space failure is swallowed: anything else
    #: is still a real fault and still raised.
    try:
        session.commit()  # the vault row, when open_with had to create one
    except Exception as exc:
        if not diskspace.out_of_space(exc):
            raise
        session.rollback()
        #: Never hold a key in memory that is not on disk. Private notes
        #: written under a wrapped DEK that never got saved would be
        #: unreadable on the next launch, which is worse than not being able
        #: to open them now.
        vault.close()
        vault_open = False
    try:
        log_action(session, "unlocked", "user", user.id)
        session.commit()
    except Exception as exc:
        if not diskspace.out_of_space(exc):
            raise
        session.rollback()
        logging.getLogger("tessellate.auth").warning(
            "unlocked without writing the audit line: the disk is full"
        )
    token = _issue_token()
    if vault_open:
        vault.grant(token)
    _grant_media(request, response, token)
    if is_another_device(request):
        _network_tokens.intersection_update(_active_tokens)
        _network_tokens.add(token)
    if device:
        lantrust.settle(device)
        _device_tokens[token] = lantrust.device_hash(device)
        lantrust.touch_device(config.data_dir, device, _client_key(request))
    return {"token": token, "vault_open": vault_open}


@router.post("/media-session", dependencies=[Depends(require_unlock)])
def media_session(request: Request, response: Response, x_auth_token: str | None = Header(default=None)) -> dict:
    """Set the media cookie again for a session the frontend already holds.

    The boot path calls this when it finds a token in localStorage: a profile
    that kept the token and lost its cookies (cleared site data, a browser
    that drops cookies on exit) would otherwise show every picture broken
    until the next unlock. `require_unlock` has already checked the header.
    """
    _grant_media(request, response, x_auth_token or "")
    return {"ok": True}


class MediaLinkIn(BaseModel):
    path: str = Field(max_length=512)


@router.post("/media-link", dependencies=[Depends(require_unlock)])
def media_link(body: MediaLinkIn, x_auth_token: str | None = Header(default=None)) -> dict:
    """A two-minute link to one `/media` or `/files` path (see MEDIA_LINK_SECONDS)."""
    path = urllib.parse.unquote(body.path)
    if not _MEDIA_LINK_PATH.fullmatch(body.path) or "/.." in path or "//" in path:
        raise HTTPException(status_code=422, detail="Only a picture or file of this notebook can open in a tab.")
    now = time.time()
    for stale in [t for t, (_, expires, _) in _media_links.items() if expires <= now]:
        del _media_links[stale]
    ticket = secrets.token_urlsafe(32)
    _media_links[ticket] = (path, now + MEDIA_LINK_SECONDS, x_auth_token or "")
    return {"url": f"{body.path}?once={ticket}"}


@router.post("/auto-session")
def auto_session(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """A session without a password, for this computer, when sign-in is off.

    Refused (403) unless `_from_this_computer` holds and the switch is off.
    The vault is not touched: private notes stay locked until
    `/auth/unlock-vault` is given the password. A token the caller already
    holds and that is still live is kept rather than replaced, because the
    boot path asks on every load and one tab must not mint a session per
    reload.
    """
    if not _auto_session_allowed(request, session, config):
        raise HTTPException(status_code=403, detail="Enter your password to unlock.")
    idle_ttl = config.get_preference("session_idle_ttl_minutes", _SESSION_IDLE_TTL // 60) * 60
    if x_auth_token and _token_valid(x_auth_token, idle_ttl):
        token = x_auth_token
    else:
        token = _issue_token()
        user = _get_user(session)
        try:
            log_action(session, "unlocked", "user", user.id, "without a password (sign-in is off)")
            session.commit()
        except Exception as exc:
            # A full disk must not lock anyone out (see `unlock`).
            if not diskspace.out_of_space(exc):
                raise
            session.rollback()
    _grant_media(request, response, token)
    # This session's answer, not the process's: another session's unlock
    # never opens private notes for one that did not give the password.
    return {"token": token, "vault_open": vault.is_granted(token)}


@router.post("/unlock-vault", dependencies=[Depends(require_unlock)])
def unlock_vault(
    body: PasswordBody,
    request: Request,
    session: Session = Depends(get_session),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Open private notes for a session that started without the password.

    The same password check as `/auth/unlock` and the same throttle, so a
    session without a password is not a second, unthrottled place to guess
    it. The session's token is kept; only the key is loaded.
    """
    client = _client_key(request)
    _refuse_if_throttled(client)
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    if not _password_matches(body.password, user.password_hash):
        _unlock_failed(client)
        raise HTTPException(status_code=401, detail="That password is wrong.")
    _unlock_succeeded(client)
    vault_open = vault.open_with(session, body.password)
    try:
        session.commit()  # the vault row, when open_with had to create one
    except Exception as exc:
        if not diskspace.out_of_space(exc):
            raise
        session.rollback()
        # Never hold a key in memory that is not on disk (see `unlock`).
        vault.close()
        vault_open = False
    if vault_open:
        vault.grant(x_auth_token)
    try:
        log_action(session, "unlocked", "vault", detail="private notes opened")
        session.commit()
    except Exception as exc:
        if not diskspace.out_of_space(exc):
            raise
        session.rollback()
    return {"vault_open": vault_open}


class PasswordOnOpenBody(BaseModel):
    enabled: bool
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_CHARS)


@router.post("/password-on-open", dependencies=[Depends(require_unlock)])
def set_password_on_open(
    body: PasswordOnOpenBody,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """Turn "Ask for a password when the app opens" on or off.

    Off needs the current password, checked and throttled exactly like an
    unlock: an unlocked screen is not proof of knowing it (the same reason
    `/auth/change-password` asks), and this is the switch that lets the next
    person at this keyboard in without it. On needs nothing, since it only
    ever asks for more.
    """
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    if not body.enabled:
        # Off lets the next person at this keyboard in without it: this
        # computer's own decision, never a phone's.
        this_computer_only(request)
        client = _client_key(request)
        _refuse_if_throttled(client)
        if not body.current_password or not _password_matches(
            body.current_password, user.password_hash
        ):
            if body.current_password:
                _unlock_failed(client)
            raise HTTPException(status_code=401, detail="That isn't your current password.")
        _unlock_succeeded(client)
    config.set_preference(PASSWORD_ON_OPEN_KEY, body.enabled)
    log_action(
        session, "edited", "user", user.id,
        f"ask for a password when the app opens: {'on' if body.enabled else 'off'}",
    )
    session.commit()
    return {"password_on_open": body.enabled}


class LanAccessBody(BaseModel):
    enabled: bool
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_CHARS)


def _lan_state(config: ConfigManager, request: Request) -> dict:
    """The switch, who can reach the app, and the certificate's fingerprint
    (core/lancert.py), which a phone user compares with the warning."""
    from tessellate.core import lancert

    info = lancert.read(config.data_dir)
    trust = lantrust.load(config.data_dir)
    here = _from_this_computer(request)
    here_key = _current_network_key(config)
    return {
        "allow_lan": netbind.lan_enabled(config),
        **netbind.describe(config, request.url.port),
        "certificate": info.public() if info else None,
        #: INBOX 867: the overrides, the remembered networks and devices, and
        #: who is waiting. Devices and requests are this computer's to see.
        "any_network": trust["any_network"],
        "ask_new_devices": trust["ask_new_devices"],
        #: One row per network (`lantrust.listed`): a Wi-Fi name over its
        #: subnet, whichever of its records were read more or less fully.
        "networks": lantrust.listed(trust["networks"], here_key),
        "devices": lantrust.devices(config.data_dir) if here else [],
        "pending": lantrust.pending() if here else [],
        #: INBOX 896: networks the port stayed closed on, and those the
        #: person stopped trusting (`blocked`), to trust or forget.
        "untrusted": [
            {**n, "blocked": bool(n.get("blocked"))}
            for n in lantrust.listed([{**n, "blocked": bool(n.get("blocked"))} for n in trust["untrusted"]], here_key)
        ],
        "current_network": here_key,
        #: INBOX 900: the switch applies while the app runs.
        "live": lanlive.attached(),
        #: When LAN mode last switched itself off for lack of use (a date).
        "switched_off": trust["switched_off"],
        "unused_days": lantrust.UNUSED_DAYS,
    }


def _current_network_key(config: ConfigManager) -> str:
    network = lantrust.current_network() if not netbind.is_loopback_bind() else None
    if network is None and netbind.lan_enabled(config):
        network = lantrust.network_for_display()
    return network.key if network is not None else ""


@router.get("/lan-access", dependencies=[Depends(require_unlock)])
def lan_access(request: Request, config: ConfigManager = Depends(get_config)) -> dict:
    """What Settings says about "Allow other devices on this network"."""
    return _lan_state(config, request)


@router.get("/lan-certificate.pem")
def download_lan_certificate(config: ConfigManager = Depends(get_config)) -> Response:
    """The authority's certificate, for a phone to install and trust (never a key).

    No unlock (INBOX 866): Settings' button is a plain navigation, because
    iOS installs a profile only from one, and a navigation carries no
    X-Auth-Token, so behind the lock it was a 401 every time. Nothing here is
    secret: every TLS handshake on the LAN port already sends this certificate.
    """
    from tessellate.core import lancert

    pem = lancert.authority_pem(config.data_dir)
    if pem is None:
        raise HTTPException(status_code=404, detail="No certificate yet. Turn on other devices first.")
    return Response(
        pem,
        media_type="application/x-x509-ca-cert",
        headers={"Content-Disposition": 'attachment; filename="memorymap-lan.crt"'},
    )


@router.post("/lan-certificate", dependencies=[Depends(require_unlock), Depends(this_computer_only)])
def regenerate_lan_certificate(
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """Settings, Other devices, "Regenerate certificate": a new key and
    certificate (core/lancert.py), handed to the running HTTPS listener so
    the next connection uses it. Every device that trusted the old one sees
    the warning once more, with the new fingerprint to compare."""
    from tessellate.core import lancert

    info = lancert.generate(config.data_dir)
    lancert.reload(info)
    log_action(session, "edited", "user", None, "made a new certificate for other devices")
    session.commit()
    return _lan_state(config, request)


def _check_password_for_lan(request: Request, session: Session, password: str | None) -> User:
    """Every loosening of LAN mode asks for the password, like the switch."""
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="Set a password first.")
    client = _client_key(request)
    _refuse_if_throttled(client)
    if not password or not _password_matches(password, user.password_hash):
        if password:
            _unlock_failed(client)
        raise HTTPException(status_code=401, detail="That isn't your current password.")
    _unlock_succeeded(client)
    return user


class LanPasswordBody(BaseModel):
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_CHARS)


class LanOptionBody(BaseModel):
    name: str = Field(pattern="^(any_network|ask_new_devices)$")
    enabled: bool
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_CHARS)


def _require_this_computer(request: Request) -> None:
    """Stricter than `this_computer_only` (the Host is checked too), and the
    same sentence, so a phone reads one refusal whichever guard said no."""
    if not _from_this_computer(request):
        raise HTTPException(status_code=403, detail=REFUSAL)


@router.post("/lan-networks/allow", dependencies=[Depends(require_unlock)])
def allow_this_network(
    body: LanPasswordBody,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """"Allow on this network": remembered, and the LAN port opens now.
    Only ever a loosening, so only from this computer (secscan-1011): a
    phone with the password must not open the port on a network the person
    at the computer never chose."""
    _require_this_computer(request)
    user = _check_password_for_lan(request, session, body.current_password)
    trust = lantrust.allow_current(config.data_dir)
    label = (trust.get("network") or {}).get("label") or "an unknown network"
    log_action(session, "edited", "user", user.id, f"allowed other devices on {label}")
    session.commit()
    return _lan_state(config, request)


@router.delete("/lan-networks/{key}", dependencies=[Depends(require_unlock)])
def forget_network(key: str, request: Request, config: ConfigManager = Depends(get_config)) -> dict:
    """Forget a network, trusted or not: only ever lets fewer in, so no
    password, but the lists are this computer's to manage (INBOX 896), as
    Stop trusting is: a phone never edits them."""
    _require_this_computer(request)
    if not lantrust.forget_network(config.data_dir, key):
        raise HTTPException(status_code=404, detail="That network is not on the list.")
    return _lan_state(config, request)


@router.post("/lan-networks/{key}/trust", dependencies=[Depends(require_unlock)])
def trust_network(
    key: str,
    body: LanPasswordBody,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """Trust a network from the untrusted list (INBOX 896): a loosening, so
    this computer only and with the password, like "Allow on this network"."""
    _require_this_computer(request)
    user = _check_password_for_lan(request, session, body.current_password)
    if not lantrust.trust_network(config.data_dir, key):
        raise HTTPException(status_code=404, detail="That network is not on the list.")
    log_action(session, "edited", "user", user.id, "trusted a network for other devices")
    session.commit()
    return _lan_state(config, request)


@router.post("/lan-networks/{key}/untrust", dependencies=[Depends(require_unlock)])
def untrust_network(key: str, request: Request, config: ConfigManager = Depends(get_config)) -> dict:
    """"Stop trusting" (INBOX 896): only ever lets fewer in, so no password,
    but this computer's list is managed from this computer."""
    _require_this_computer(request)
    if not lantrust.untrust_network(config.data_dir, key):
        raise HTTPException(status_code=404, detail="That network is not on the list.")
    return _lan_state(config, request)


@router.post("/lan-notice/dismiss", dependencies=[Depends(require_unlock)])
def dismiss_lan_notice(request: Request, config: ConfigManager = Depends(get_config)) -> dict:
    """The "switched itself off after 14 days" notice was read."""
    _require_this_computer(request)
    lantrust.clear_switched_off(config.data_dir)
    return _lan_state(config, request)


@router.post("/lan-options", dependencies=[Depends(require_unlock)])
def set_lan_option(
    body: LanOptionBody,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """"Allow on any network" and "Ask before a new device signs in". The
    looser setting of each asks for the password; the safer needs nothing."""
    looser = body.enabled if body.name == "any_network" else not body.enabled
    if looser:
        # The looser direction is this computer's call (secscan-1011), as
        # `answer_device` is; the safer one is open to any signed-in device.
        _require_this_computer(request)
        user = _check_password_for_lan(request, session, body.current_password)
        log_action(session, "edited", "user", user.id, f"other devices: {body.name.replace('_', ' ')} {'on' if body.enabled else 'off'}")
        session.commit()
    lantrust.set_flag(config.data_dir, body.name, body.enabled)
    return _lan_state(config, request)


@router.post("/lan-devices/{device_id}/{verdict}", dependencies=[Depends(require_unlock)])
def answer_device(
    device_id: str,
    verdict: str,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """Allow or Deny a device waiting to sign in: this computer only, since
    the point is that someone here says yes."""
    _require_this_computer(request)
    if verdict not in ("allow", "deny"):
        raise HTTPException(status_code=404, detail="Allow or deny.")
    held = {p["id"]: p for p in lantrust.pending()}.get(device_id)
    if held is None or not lantrust.decide(config.data_dir, device_id, verdict == "allow"):
        raise HTTPException(status_code=404, detail="That device is no longer waiting.")
    log_action(session, "edited", "user", None, f"{'allowed' if verdict == 'allow' else 'refused'} {held['name']} at {held['address']}")
    session.commit()
    return _lan_state(config, request)


@router.delete("/lan-devices/{device_id}", dependencies=[Depends(require_unlock)])
def forget_device(device_id: str, request: Request, config: ConfigManager = Depends(get_config)) -> dict:
    """Remove an allowed device: it asks again next time, and its open
    sessions end now."""
    if not lantrust.forget_device(config.data_dir, device_id):
        raise HTTPException(status_code=404, detail="That device is not on the list.")
    for token in [t for t, owner in _device_tokens.items() if owner == device_id]:
        _device_tokens.pop(token, None)
        _active_tokens.pop(token, None)
        vault.revoke([token])
    _forget_dead_tickets()
    return _lan_state(config, request)


WATCH_SECONDS = 25.0
WATCH_SLICE_SECONDS = 5.0


@router.get("/lan-watch", dependencies=[Depends(require_unlock)])
async def lan_watch(request: Request, since: int = -1, config: ConfigManager = Depends(get_config)) -> dict:
    """This computer's window waits here for a device to ask, or the network
    to change, so its notice comes at once rather than at the next poll. No
    thread is held while it waits."""
    _require_this_computer(request)
    deadline = time.monotonic() + WATCH_SECONDS
    #: Woken by the change itself; the slices only let a closed tab end the wait.
    while time.monotonic() < deadline and not await request.is_disconnected():
        if await lantrust.wait_version_change(since, min(WATCH_SLICE_SECONDS, deadline - time.monotonic())):
            break
    trust = lantrust.status()
    serving = not netbind.is_loopback_bind() and trust["reason"] != "off"
    return {
        "version": lantrust.version(),
        "serving": serving,
        "held": None if trust["open"] or not serving else trust,
        "pending": lantrust.pending(),
        #: The status bar's LAN icon (INBOX 896): on, open, the reason it is
        #: closed, and a switched-off notice; the window waits here, so a
        #: network change reaches the icon within the watch's own beat.
        "allow_lan": netbind.lan_enabled(config),
        "live": lanlive.attached(),
        "error": lanlive.last_error(),
        "network": (trust["network"] or {}).get("label", "") if serving else "",
        "reason": trust["reason"] if serving else "",
        "switched_off": lantrust.load(config.data_dir)["switched_off"],
    }


@router.post("/lan-access", dependencies=[Depends(require_unlock)])
def set_lan_access(
    body: LanAccessBody,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """Turn LAN mode on or off, for the next launch (WORLD_CLASS_PLAN §12).

    On needs the current password, checked and throttled like an unlock, for
    the reason `/auth/password-on-open` gives: an unlocked screen is not proof
    of knowing it, and this is the switch that puts the notebook on the
    network. Off needs nothing, since it only ever lets fewer in. The bind
    happens at launch (`__main__._run_server`), so the answer says whether a
    restart is still needed; nothing here opens a socket.
    """
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="Set a password first.")
    if body.enabled:
        this_computer_only(request)  # opening the network is this computer's call
        client = _client_key(request)
        _refuse_if_throttled(client)
        if not body.current_password or not _password_matches(
            body.current_password, user.password_hash
        ):
            if body.current_password:
                _unlock_failed(client)
            raise HTTPException(status_code=401, detail="That isn't your current password.")
        _unlock_succeeded(client)
        # A password from before the eight-character floor can be a 4-digit
        # PIN, which the throttle slows but a network full of strangers (a
        # campus wifi) has all day to try. The password is in hand only here.
        if len(body.current_password) < NEW_PASSWORD_MIN_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f"Change your password to at least {NEW_PASSWORD_MIN_CHARS} characters before letting other devices in.",
            )
    config.set_preference(netbind.LAN_PREF, body.enabled)
    ended = 0
    if body.enabled:
        # Made now, so Settings can show the fingerprint before a phone ever
        # connects (core/lancert.py).
        from tessellate.core import lancert

        lancert.ensure(config.data_dir)
        # INBOX 867: the network it was turned on in is the one it opens on.
        lantrust.remember_current(config.data_dir)
        lantrust.mark_turned_on(config.data_dir)
    else:
        # Off means off now: every other device is signed out, and the
        # listener below drops their connections (INBOX 900).
        ended = _end_network_sessions()
    #: INBOX 900: the launcher's supervisor opens or closes the LAN port now;
    #: the answer waits for it, so `restart_required` says what is true.
    live = lanlive.attached()
    if live:
        lanlive.wait_pass(lanlive.wake())
    log_action(
        session, "edited", "user", user.id,
        f"allow other devices on this network: {'on' if body.enabled else 'off'}"
        + ("" if live else " (from the next launch)")
        + (f", {ended} other device(s) signed out" if ended else ""),
    )
    session.commit()
    return _lan_state(config, request)


@router.post("/lock")
def lock(
    request: Request,
    response: Response,
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Log out: the token stops working immediately, and its media ticket too.

    Only for a session that exists (SEC-05, security audit 2026-10-05). This
    route is open and takes no body, so any web page could fire it as a
    no-cors POST, and with sign-in off it closed the owner's vault for them.
    A request without a live token has nothing to log out of, so nothing
    happens; the answer is the same, so a page learns nothing from it.
    """
    if not x_auth_token or x_auth_token not in _active_tokens:
        return {"locked": True}
    _active_tokens.pop(x_auth_token or "", None)
    #: A notification left on screen must not act on a notebook that is locked.
    reminder_token.rotate(get_config().data_dir)
    _forget_dead_tickets()
    _revoke_media(request, response)
    vault.revoke([x_auth_token or ""])
    # Forget the data key too, or "lock" would leave private notes readable.
    # With sign-in off, always: the next load starts a session without a
    # password, and it must not find the key another session left loaded.
    if not _active_tokens or not password_on_open(config):
        vault.close()
    return {"locked": True}


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)
    new_password: str = Field(
        min_length=4, max_length=MAX_PASSWORD_CHARS, description="The new password, 8+ characters"
    )


@router.get("/account", dependencies=[Depends(require_unlock)])
def account(
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """What Settings → Account needs to describe the current state.

    Deliberately says nothing secret: whether a password exists, whether the
    vault is open, and how many sessions are live.
    """
    user = _get_user(session)
    idle_ttl = config.get_preference("session_idle_ttl_minutes", _SESSION_IDLE_TTL // 60) * 60
    _sweep_expired(idle_ttl)  # or the session count reports tokens that no longer work
    return {
        "configured": user is not None,
        "username": user.username if user else None,
        "created_at": user.created_at.isoformat() if user and user.created_at else None,
        # For this session: see `vault._granted`.
        "vault_open": vault.key() is not None,
        "vault_exists": vault.exists(session),
        "active_sessions": len(_active_tokens),
        "password_on_open": password_on_open(config),
        # When the recovery key was made, or None: Settings says which button
        # to show (INBOX 663). Behind the lock, unlike `/auth/status`.
        "recovery_key_created_at": _iso(vault.recovery_created_at(session)),
        # Settings > Security: whether this computer can keep a PIN, whether
        # one is set, and whether the caller is this computer (only it may).
        "pin": {
            "available": pinstore.available(config.data_dir),
            "set": pinstore.is_set(config.data_dir),
            "here": _from_this_computer(request),
        },
    }


def _iso(when) -> str | None:  # noqa: ANN001  # datetime | None
    return when.isoformat() if when else None


@router.post("/change-password", dependencies=[Depends(require_unlock)])
def change_password(
    body: ChangePasswordBody,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Change the password, re-wrapping the vault key onto the new one.

    The current password is required even though the caller already holds a
    valid token. The token proves the session is unlocked; it does not prove
    the person at the keyboard knows the password, and this is the one action
    that can lock someone out of their own private notes.

    Order matters. The vault is re-wrapped BEFORE the password hash changes,
    because a failure between the two would otherwise leave a notebook whose
    password no longer opens its own private notes.
    """
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    # SEC-04 (audit 2026-10-05): the unlock throttle, or a session that never
    # gave the password (sign-in off) could guess it here at bcrypt speed.
    client = _client_key(request)
    _refuse_if_throttled(client)
    if not _password_matches(body.current_password, user.password_hash):
        _unlock_failed(client)
        raise HTTPException(status_code=401, detail="That isn't your current password.")
    _unlock_succeeded(client)
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="That's already your password.")
    problem = _new_password_problem(body.new_password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    if vault.exists(session) and vault.key() is None:
        # A session started without a password (sign-in off) has the vault
        # locked, and the current password just checked above is exactly
        # what opens it, for this session.
        vault.open_with(session, body.current_password)
        vault.grant(x_auth_token)
    if vault.exists(session) and vault.key() is None:
        # Without the data key in hand the vault cannot be re-wrapped, and
        # changing the password anyway would strand every private note.
        raise HTTPException(
            status_code=409,
            detail="Unlock the app before changing your password, so your "
            "private notes can be moved across to it.",
        )
    if vault.exists(session) and not vault.rewrap(session, body.new_password):
        raise HTTPException(
            status_code=500, detail="Couldn't move your private notes to the new password."
        )

    user.password_hash = _hash_password(body.new_password)
    log_action(session, "edited", "user", user.id, "password changed")
    session.commit()
    # The PIN record is bound to the old hash, so it could open nothing now;
    # it is cleared rather than re-wrapped, since re-wrapping needs the PIN.
    pin_cleared = pinstore.forget(get_config().data_dir)

    # Every other session is invalidated: a password change is exactly when
    # you want anything already open elsewhere to stop working. The caller
    # keeps working via a freshly issued token.
    _active_tokens.pop(x_auth_token or "", None)
    signed_out = len(_active_tokens)
    _active_tokens.clear()
    _media_tickets.clear()
    vault.revoke_all()
    token = _issue_token()
    vault.grant(token)
    _grant_media(request, response, token)
    return {
        "changed": True,
        "token": token,
        "other_sessions_ended": signed_out,
        "warning": password_warning(body.new_password),
        "pin_cleared": pin_cleared,
    }


# --- the PIN for this computer (owner, 2026-10-12; core/pinstore.py) ---------------


class PinBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)
    pin: str = Field(min_length=4, max_length=12, description="4 to 12 digits")


class ForgetPinBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)


def _check_current_password(request: Request, session: Session, typed: str) -> User:
    """The password, never the PIN: throttled and counted like an unlock."""
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    client = _client_key(request)
    _refuse_if_throttled(client)
    if not _password_matches(typed, user.password_hash):
        _unlock_failed(client)
        raise HTTPException(status_code=401, detail="That isn't your current password.")
    _unlock_succeeded(client)
    return user


@router.post("/pin", dependencies=[Depends(require_unlock), Depends(this_computer_only)])
def set_pin(
    body: PinBody,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Set up or replace the PIN for this computer, behind the password.

    `this_computer_only` refuses other devices; `_from_this_computer` also
    refuses a tunnel on this machine, since a PIN set there is one only a
    tunnel could use, and a tunnel never may.
    """
    if not _from_this_computer(request):
        raise HTTPException(status_code=403, detail=REFUSAL)
    if not pinstore.valid_pin(body.pin):
        raise HTTPException(status_code=400, detail="A PIN is 4 to 12 digits.")
    user = _check_current_password(request, session, body.current_password)
    if not pinstore.available(config.data_dir):
        raise HTTPException(
            status_code=409,
            detail="This computer has no protected store for a PIN, so the password is the only way in here.",
        )
    if vault.key() is None:
        vault.open_with(session, body.current_password)
        session.commit()  # the vault row, when open_with had to create one
        vault.grant(x_auth_token)
    dek, bound = vault.key(), _pin_binding(session, user)
    if dek is None or bound is None:
        raise HTTPException(status_code=409, detail="Unlock your private notes before setting up a PIN.")
    try:
        pinstore.save(config.data_dir, body.pin, dek, bound)
    except pinstore.StoreError:
        raise HTTPException(
            status_code=409,
            detail="This computer's protected store did not keep the PIN. The password still works.",
        ) from None
    log_action(session, "edited", "user", user.id, "PIN set up on this computer")
    session.commit()
    return {"set": True}


@router.post("/pin/forget", dependencies=[Depends(require_unlock), Depends(this_computer_only)])
def forget_pin(
    body: ForgetPinBody,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """Settings > Security, "Forget PIN": the password, then it is gone."""
    user = _check_current_password(request, session, body.current_password)
    forgotten = pinstore.forget(config.data_dir)
    if forgotten:
        log_action(session, "edited", "user", user.id, "PIN removed from this computer")
        session.commit()
    return {"forgotten": forgotten}


class RotateVaultKeyBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)


@router.post("/rotate-vault-key", dependencies=[Depends(require_unlock)])
def rotate_vault_key(
    body: RotateVaultKeyBody,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Re-key the vault: a fresh DEK, with every private note moved onto it.

    `/change-password` deliberately does NOT do this, see crypto.py's own
    design note. It only re-wraps the DEK (32 bytes); the DEK ITSELF never
    changes, on purpose, so an ordinary password change can't touch a single
    note. That is the right trade for that endpoint, but it leaves exactly
    one long-lived secret in this app that nothing ever rotates: the key
    that actually encrypts every private note. If an old wrapped-DEK ever
    got out: a stolen backup made before a password change, a copied
    database file: it still opens *today's* notes, because they are still
    under the very same DEK the backup was wrapped around. This endpoint is
    the fix for that: generate a new DEK and move every note onto it, so an
    old exposure stops mattering.

    All-or-nothing, deliberately paranoid (this is the HIGH RISK direction
    CLAUDE.md calls out for this exact feature): every note is decrypted
    with the OLD key and re-encrypted with the NEW one entirely in memory
    first; nothing is written to the database, and the in-memory key is not
    swapped, until every note round-trips cleanly under the new key AND the
    vault row's re-wrap succeeds: all inside the one commit below. A
    DecryptionError, a crash, or any other exception before that commit
    leaves the OLD key and OLD ciphertext exactly as they were; there is no
    step where a note is only half-migrated.
    """
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    # SEC-04 (audit 2026-10-05): the unlock throttle, or a session that never
    # gave the password (sign-in off) could guess it here at bcrypt speed.
    client = _client_key(request)
    _refuse_if_throttled(client)
    if not _password_matches(body.current_password, user.password_hash):
        _unlock_failed(client)
        raise HTTPException(status_code=401, detail="That isn't your current password.")
    _unlock_succeeded(client)

    if not vault.exists(session):
        raise HTTPException(status_code=400, detail="There are no private notes to re-encrypt yet.")
    if vault.key() is None:
        vault.open_with(session, body.current_password)  # see change-password
        vault.grant(x_auth_token)
    old_key = vault.key()
    if old_key is None:
        raise HTTPException(
            status_code=409,
            detail="Unlock the app before rotating the encryption key.",
        )

    # "all": every note in every workspace, deleted or not, a note this
    # misses would be left encrypted under the OLD key forever, because the
    # vault row (and therefore the only wrapped copy of that key) is about to
    # point at the NEW one instead.
    session.info["workspace_id"] = "all"
    private_entries = [
        entry
        for entry in session.scalars(select(Entry))
        if crypto.is_encrypted(entry.content)
    ]

    new_key = crypto.new_dek()

    # Decrypt with the OLD key and re-encrypt with the NEW one, entirely in
    # memory, before a single ORM object is touched.
    #
    # **A note the current key cannot open is left exactly as it is** (INBOX
    # 663). Until the reset was a button on the lock screen this raised, and
    # a notebook reset without its recovery key could never re-key again: its
    # sealed private notes were made under the vault the reset removed, so
    # the current key opens none of them, and one was enough for a 500
    # (measured on the forgotpw.js data dir, 2026-10-06). Leaving such a note
    # is safe in the one direction this guard exists for: it is unreadable by
    # the current key before the re-key and after it, so nothing that could
    # be read becomes unreadable. Its ciphertext is not touched, so its own
    # old key (in an old backup's vault row) still opens it.
    rewritten = []
    sealed = 0
    for entry in private_entries:
        try:
            plaintext = crypto.decrypt(old_key, entry.content)
        except crypto.DecryptionError:
            sealed += 1
            continue
        rewritten.append((entry, plaintext, crypto.encrypt(new_key, plaintext)))

    # Verify the round trip against the REAL ciphertext just produced, not a
    # throwaway marker, before any of it becomes the only copy on disk.
    for entry, plaintext, new_ciphertext in rewritten:
        if crypto.decrypt(new_key, new_ciphertext) != plaintext:
            raise HTTPException(
                status_code=500,
                detail="The re-encrypted notes did not check out, so nothing was changed.",
            )

    for entry, _plaintext, new_ciphertext in rewritten:
        entry.content = new_ciphertext
    manager.rekey_private_extras(session, old_key, new_key)

    vault_row = session.scalar(select(Vault))
    new_salt = crypto.new_salt()
    vault_row.kdf_salt = new_salt
    vault_row.wrapped_dek = crypto.wrap_dek(new_key, body.current_password, new_salt)
    # The recovery key wraps the OLD key, and the old key is exactly what a
    # re-key exists to make worthless (INBOX 663). So a notebook that had one
    # is handed its successor, wrapping the new key, in the same commit; the
    # old one is dead from here. One without a key stays without.
    recovery_key = vault.issue_recovery(session, new_key) if vault_row.recovery_wrapped_dek else None

    log_action(
        session, "edited", "vault",
        detail=f"encryption key rotated ({len(rewritten)} note(s) re-encrypted)",
    )
    session.commit()  # one transaction: every note and the vault row, or none

    # Only now, after the commit that made it real, does memory follow.
    vault.set_key(new_key)
    # The PIN wraps the old key, which is what a re-key exists to retire.
    pinstore.forget(get_config().data_dir)

    # Same reasoning as change-password: rotating a key you suspect is
    # compromised should not leave anything already open still trusted on
    # the old one.
    _active_tokens.pop(x_auth_token or "", None)
    ended = len(_active_tokens)
    _active_tokens.clear()
    _media_tickets.clear()
    vault.revoke_all()
    token = _issue_token()
    vault.grant(token)
    _grant_media(request, response, token)
    return {
        "rotated": True,
        "notes_reencrypted": len(rewritten),
        "notes_sealed": sealed,
        "token": token,
        "other_sessions_ended": ended,
        "recovery_key": recovery_key,
    }


# --- forgot your password? (INBOX 663) --------------------------------------
#
# Three routes. `/recovery-key` makes or replaces the key from Settings (or
# the step after setup), behind the lock and the current password. The other
# two are the lock screen's "Forgot your password?" card, and so are open:
# whoever calls them has, by definition, no password. What stands in for it:
#
# - **This computer only.** `_from_this_computer`: a loopback connection, no
#   forwarding header, a loopback Host (the DNS-rebinding door). A phone on
#   the network is told to do it at the computer the notebook lives on; a
#   reset is a change to the notebook's own files and belongs at its keyboard,
#   where the terminal command already was. The Origin check (core/security.py)
#   still stands in front, so another site's page cannot fire them either.
# - `/recover` needs the recovery key, and wrong keys earn the same waits as
#   wrong passwords (the same buckets: a guess is a guess).
# - `/reset` needs the word RESET typed, which only stops an accident; the
#   person at this keyboard could always run the terminal command.
#
# Nothing either says depends on the notebook's contents: no note counts, no
# "this notebook has no recovery key". A missing key and a wrong one are the
# same 401, so a passer-by learns nothing by trying.

RESET_WORD = "RESET"
_RECOVERY_KEY_MAX_CHARS = 200  # a key is 39 with its dashes; room for spaces


class RecoveryKeyBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)


class RecoverBody(BaseModel):
    recovery_key: str = Field(min_length=1, max_length=_RECOVERY_KEY_MAX_CHARS)
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)


class ResetBody(BaseModel):
    confirm: str = Field(default="", max_length=32)


def _refuse_unless_this_computer(request: Request) -> None:
    if not _from_this_computer(request):
        raise HTTPException(
            status_code=403,
            detail="Reset your password on the computer this notebook lives on.",
        )


def _end_sessions_and_issue(request: Request, response: Response) -> str:
    """Every session and every vault grant ends; the caller gets a new one."""
    _active_tokens.clear()
    _media_tickets.clear()
    vault.revoke_all()
    token = _issue_token()
    vault.grant(token)
    _grant_media(request, response, token)
    return token


@router.post("/recovery-key", dependencies=[Depends(require_unlock)])
def make_recovery_key(
    body: RecoveryKeyBody,
    request: Request,
    session: Session = Depends(get_session),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Make a recovery key, or replace the one there is. Shown once.

    The current password, checked and throttled like an unlock, for the
    reason `/auth/change-password` gives: an unlocked screen is not proof of
    knowing it, and this hands out a second way into private notes.
    """
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    client = _client_key(request)
    _refuse_if_throttled(client)
    if not _password_matches(body.current_password, user.password_hash):
        _unlock_failed(client)
        raise HTTPException(status_code=401, detail="That isn't your current password.")
    _unlock_succeeded(client)
    if vault.key() is None:
        # A session without the password (sign-in off): the one just checked
        # opens the vault for it, as change-password does.
        vault.open_with(session, body.current_password)
        vault.grant(x_auth_token)
    recovery_key = vault.issue_recovery(session, vault.key())
    if recovery_key is None:
        raise HTTPException(status_code=409, detail="Unlock the app before making a recovery key.")
    log_action(session, "edited", "vault", detail="recovery key made")
    session.commit()
    return {
        "recovery_key": recovery_key,
        "recovery_key_created_at": _iso(vault.recovery_created_at(session)),
    }


class SaveRecoveryKeyBody(BaseModel):
    #: The text of the .txt the page built: the key and a few lines on what it
    #: is for. Short by construction; the cap only bounds a stray request.
    text: str = Field(min_length=1, max_length=4000)


RECOVERY_KEY_FILE = "tessellate-recovery-key.txt"


@router.post("/recovery-key/save", dependencies=[Depends(require_unlock), Depends(this_computer_only)])
def save_recovery_key(body: SaveRecoveryKeyBody, config: ConfigManager = Depends(get_config)) -> dict:
    """Download .txt in the desktop window: a native Save dialog (INBOX 671).

    Never `/files/save`, whose exports folder sits inside the data dir: a key
    beside the notebook opens its private notes for whoever copies the folder.
    The dialog starts in Documents, and a place inside the data dir is refused
    even when chosen by hand. A browser tab never comes here; it downloads.
    The text is written and forgotten: not logged, not in the audit trail.
    """
    if os.getenv("TESSELLATE_DESKTOP") != "1":
        raise HTTPException(status_code=409, detail="Only the desktop app shows a Save dialog.")

    chosen = desktop_dialog.save_dialog(RECOVERY_KEY_FILE, desktop_dialog.documents_folder())
    if chosen is None:
        return {"saved": False}
    target = chosen.expanduser().resolve()
    notebook = Path(config.data_dir).expanduser().resolve()
    if target == notebook or notebook in target.parents:
        raise HTTPException(
            status_code=400,
            detail="Save it outside the notebook's own folder, or anyone who copies the folder gets the key.",
        )
    try:
        target.write_text(body.text, encoding="utf-8")
    except OSError:
        raise HTTPException(status_code=400, detail="Couldn't save there. Choose another folder.") from None
    return {"saved": True, "path": str(target)}


@router.post("/recover")
def recover(
    body: RecoverBody,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict:
    """"I have my recovery key": a new password, private notes kept.

    In this order, each step refusing before anything is written: this
    computer, the wait a run of wrong guesses has earned, the new password's
    own rules (a 400 that says nothing about the key), the key's shape (a 400
    that says nothing about the notebook), then the key itself. On success,
    in one commit: the DEK the key unwrapped is wrapped by the new password,
    the hash changes, and a new recovery key replaces the used one. Then
    every session and vault grant ends, and the caller is handed a new one.
    """
    _refuse_unless_this_computer(request)
    client = _client_key(request)
    _refuse_if_throttled(client)
    user = _get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    problem = _new_password_problem(body.new_password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    if crypto.normalise_recovery_key(body.recovery_key) is None:
        raise HTTPException(
            status_code=400,
            detail="A recovery key is 32 letters and digits in eight groups of four. Check it and try again.",
        )
    dek = vault.open_with_recovery(session, body.recovery_key)
    if dek is None:
        _unlock_failed(client)
        raise HTTPException(status_code=401, detail="That recovery key is wrong.")
    _unlock_succeeded(client)
    vault.rewrap_with(session, dek, body.new_password)
    user.password_hash = _hash_password(body.new_password)
    # Spent: its wrap is overwritten by the successor's in this commit.
    new_key = vault.issue_recovery(session, dek)
    log_action(session, "edited", "user", user.id, "password reset with the recovery key")
    session.commit()
    vault.set_key(dek)  # only after the commit, as `rotate_vault_key` does
    pinstore.forget(get_config().data_dir)  # bound to the old password hash
    _owner_seen.clear()
    token = _end_sessions_and_issue(request, response)
    return {
        "token": token,
        "vault_open": True,
        "recovery_key": new_key,
        "warning": password_warning(body.new_password),
    }


@router.post("/reset")
def reset(
    body: ResetBody,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """"I don't have it": the terminal's `--reset-password`, from the card.

    `core.password_reset.reset_password` does the work for both doors, so the
    notebook they leave is the same. Then every session ends here, the key
    in memory is forgotten, and the app goes to first-run setup.
    """
    _refuse_unless_this_computer(request)
    if body.confirm.strip() != RESET_WORD:
        raise HTTPException(status_code=400, detail="Type RESET to confirm.")
    if _get_user(session) is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    password_reset.reset_password(session, config)
    end_every_session()
    _revoke_media(request, response)
    _clear_unlock_failures()
    return {"reset": True}


@router.post("/lock-all", dependencies=[Depends(require_unlock)])
def lock_all(request: Request, response: Response) -> dict:
    """End every session, including this one. The panic button."""
    ended = len(_active_tokens)
    _active_tokens.clear()
    _media_tickets.clear()
    _revoke_media(request, response)
    vault.close()
    return {"locked": True, "sessions_ended": ended}


def _notebook_has_password_now() -> bool:
    from tessellate.core import deps

    with deps.get_db().session() as session:
        return _password_set(session)


# The body-size cap and the LAN gate (core/security.py) ask these two.
security.register_auth(_active_tokens, _notebook_has_password_now)
