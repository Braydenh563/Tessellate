"""The unlocked data key, for as long as the app is unlocked.

The DEK lives here in memory and nowhere else. Locking, restarting, or simply
never unlocking all leave private notes unreadable, which is the intended
behaviour rather than a limitation.

Kept apart from the auth routes so the read/write paths can ask "is the vault
open?" without importing the API layer.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import crypto
from tessellate.core.database import LinkReason, Vault, utcnow

# Set on unlock, cleared on lock. Deliberately module-level: this app is
# single-user, and one process holds one notebook, so there is one key.
_dek: bytes | None = None

# **Who may use it** (OPEN.md, auth-optional: "after a LAN device unlocks, a
# loopback session without a password reads private notes too"). Holding the
# key once is right; handing it to every request was not. With sign-in off,
# this computer gets a session without the password, and a phone on the
# network that *did* give it loaded the key for everyone. So the key is now
# granted per session: the tokens of the sessions that proved the password
# (setup, unlock, unlock-vault, and the two account routes that ask for it
# again). `key()` answers a request only for a granted session.
#
# The rule starts with the first grant. A key loaded with nobody granted is
# one opened outside any session (the direct calls tests and scripts make),
# and it behaves as it always did. In the running app the two move together:
# every route that loads the key grants its caller, and the key is forgotten
# when the last granted session ends (`revoke`).
_granted: set[str] = set()

#: The session token of the request being served. Set by
#: `routes_auth.VaultScope`, an ASGI middleware, from the X-Auth-Token header;
#: FastAPI copies the context into the threadpool that runs sync routes and
#: dependencies, and into a streaming body's iterator, so every read on a
#: request's behalf sees it. `_OUTSIDE` is no request at all: a background
#: thread, which is never handed a granted key once a grant exists: the AI is
#: kept away from private notes on purpose. A job a session started on its
#: own private space's files runs as that session instead (`acting_for`).
_OUTSIDE = object()
_request_token: ContextVar[object] = ContextVar("vault_request_token", default=_OUTSIDE)

#: Whether the key now loaded was loaded outside any request: a script's or
#: a test's direct `create`/`open_with`/`set_key`, with no session to grant.
#: Such a key is the process key for every request until the first grant,
#: as it always was. A key loaded *inside* a request (`unlock`, `setup`,
#: `unlock-vault`, the two account routes) is nobody's until granted, so the
#: lines between loading it and granting the caller answer no other request.
_process_key = False


def _loaded() -> None:
    global _process_key
    _process_key = _request_token.get() is _OUTSIDE


def is_open() -> bool:
    """Whether the key is loaded at all, for anyone. The process's answer:
    what a caller may read is `key()`, or `is_granted(token)`."""
    return _dek is not None


def key() -> bytes | None:
    """The key, if the caller may use it (see `_granted`).

    Inside a request (`request_scope`), only a granted session's, whatever
    the grant set holds: an empty set means nobody, never everybody. The
    first version read an empty set as "the rule has not started" and gave
    every request the key, and the app has two gaps where the key is loaded
    with no grant yet (`unlock` loads then grants; `change-password` and
    `rotate-vault-key` clear every grant, then grant the new session), each
    wide enough for a sync route in the threadpool beside it (the review,
    2026-09-26; tests/test_vault_sessions). A key loaded outside any request
    (`_process_key`: a script, a test's direct call) is still every
    request's until the first grant. Outside a request (a background
    thread) the process key is answered until the first grant, and nothing
    after it: the background has no business with a private note once a
    person is reading them.
    """
    if _dek is None:
        return None
    token = _request_token.get()
    if token is _OUTSIDE:
        return None if _granted else _dek
    if isinstance(token, str) and token in _granted:
        return _dek
    return _dek if _process_key and not _granted else None


def grant(token: str | None) -> None:
    """Let this session use the loaded key. Only after the password was checked."""
    if token and _dek is not None:
        _granted.add(token)


def is_granted(token: str | None) -> bool:
    return bool(token) and _dek is not None and token in _granted


#: Told which sessions ended (None: every one), so what a job was handed for
#: a session goes with it (`docreader.forget_sessions`, SECURITY.md T28).
ended_hooks: list[Callable[[list[str] | None], None]] = []


def _ended(tokens: list[str] | None) -> None:
    for hook in ended_hooks:
        hook(tokens)


def revoke(tokens) -> None:  # noqa: ANN001  # any iterable of tokens
    """These sessions are over. The key goes with the last one granted."""
    global _dek
    had = bool(_granted)
    tokens = list(tokens)
    for token in tokens:
        _granted.discard(token)
    if had and not _granted:
        _dek = None
    _ended(tokens)


def revoke_all() -> None:
    """End every grant but keep the key: a password change or a re-key ends
    every other session and grants the new one straight after."""
    _granted.clear()
    _ended(None)


@contextmanager
def request_scope(token: str | None) -> Iterator[None]:
    """Serve one request as the session `token` (None: a request with none)."""
    reset = _request_token.set(token)
    try:
        yield
    finally:
        _request_token.reset(reset)


def requester() -> str | None:
    """The granted session this request is served as, or None: what a route
    hands the background job it starts, so the job reads a private space's
    sealed files as that session (`acting_for`, SECURITY.md T28)."""
    token = _request_token.get()
    return token if isinstance(token, str) and token in _granted else None


@contextmanager
def acting_for(token: str | None) -> Iterator[None]:
    """Run background work as the session `token` (from `requester`).

    **The job borrows the session's grant, never the key** (L-world-class-381).
    Nothing is copied: every `key()` inside the block asks again whether
    `token` is still granted, so the key stops answering the moment that
    session ends (lock, sign-out, expiry, a password change), whatever the
    job is doing, and the token itself lives only in the job's memory. With
    no token the block is plain background work, as before.
    """
    if token is None:
        yield
        return
    with request_scope(token):
        yield


def close() -> None:
    """Forget the key and every grant. Called on lock and by tests."""
    global _dek
    _dek = None
    _granted.clear()
    _ended(None)


def _row(session: Session) -> Vault | None:
    return session.scalar(select(Vault))


def exists(session: Session) -> bool:
    return _row(session) is not None


def create(session: Session, password: str) -> None:
    """Set up the vault on first run, and open it.

    Called from setup, so a notebook always has somewhere to put a private
    note: asking the user to "enable encryption" later would mean a second
    password prompt and a second chance to lose access.
    """
    global _dek
    if _row(session) is not None:
        return
    salt = crypto.new_salt()
    dek = crypto.new_dek()
    session.add(Vault(kdf_salt=salt, wrapped_dek=crypto.wrap_dek(dek, password, salt)))
    session.flush()
    _dek = dek
    _loaded()


def open_with(session: Session, password: str) -> bool:
    """Unwrap the DEK on unlock. False if there's no vault or it won't open.

    A notebook created before this feature existed has no vault row; one is
    created on the next unlock so private notes work from then on, without
    touching anything already written.
    """
    global _dek
    row = _row(session)
    if row is None:
        create(session, password)
        return True
    try:
        _dek = crypto.unwrap_dek(bytes(row.wrapped_dek), password, bytes(row.kdf_salt))
        _loaded()
    except crypto.DecryptionError:
        _dek = None
        return False
    return True


def set_key(dek: bytes) -> None:
    """Replace the in-memory DEK after a key rotation.

    Only ever called AFTER the rotation's database commit has already
    succeeded. Swapping the key first, or on any path that might still
    fail: would leave memory holding a key that disagrees with what is
    actually on disk if the process died between the two.
    """
    global _dek
    _dek = dek
    _loaded()


def rewrap(session: Session, new_password: str) -> bool:
    """Point the vault at a new password. Notes are never re-encrypted.

    Only possible while unlocked, because the DEK has to be in hand, which
    also means a password change can't be used to lock yourself out.
    """
    row = _row(session)
    if row is None or _dek is None:
        return False
    salt = crypto.new_salt()
    row.kdf_salt = salt
    row.wrapped_dek = crypto.wrap_dek(_dek, new_password, salt)
    return True


# --- the recovery key (INBOX 663) ------------------------------------------
#
# A second wrap of the same DEK, by a key the owner keeps somewhere else. Four
# moves, and each one leaves at most one recovery key that works:
#
#   make or replace  `issue_recovery`  needs the DEK in hand (unlocked)
#   use              `open_with_recovery` then `issue_recovery` again: a used
#                    key is spent, so the reset hands out its successor
#   re-key           the rotation calls `issue_recovery` with the new DEK when
#                    a key existed, since the old one wraps the old DEK
#   reset without it the vault row goes, and with it every wrap
#
# The key string is a local in each of these and nothing else: never a
# column, never a log line, never an audit detail.


def recovery_created_at(session: Session):  # noqa: ANN201  # datetime | None
    row = _row(session)
    return row.recovery_created_at if row is not None and row.recovery_wrapped_dek else None


def issue_recovery(session: Session, dek: bytes | None = None) -> str | None:
    """Wrap the DEK (the loaded one, or `dek`) under a fresh recovery key and
    return the key, to be shown once. Any earlier key stops working, because
    its wrap is overwritten in the same row. None without a vault or a key."""
    row = _row(session)
    dek = dek if dek is not None else _dek
    if row is None or dek is None:
        return None
    recovery_key = crypto.new_recovery_key()
    canonical = crypto.normalise_recovery_key(recovery_key)
    salt = crypto.new_salt()
    row.recovery_salt = salt
    row.recovery_wrapped_dek = crypto.wrap_dek(dek, canonical, salt)
    row.recovery_created_at = utcnow()
    return recovery_key


def open_with_recovery(session: Session, typed: str) -> bytes | None:
    """The DEK the recovery key unwraps, or None: no vault, no recovery key,
    not a key's shape, or the wrong key. The caller cannot tell these apart
    on purpose (see `routes_auth.recover`). Nothing is loaded into memory."""
    row = _row(session)
    canonical = crypto.normalise_recovery_key(typed)
    if row is None or not row.recovery_wrapped_dek or not row.recovery_salt or canonical is None:
        return None
    try:
        return crypto.unwrap_dek(bytes(row.recovery_wrapped_dek), canonical, bytes(row.recovery_salt))
    except crypto.DecryptionError:
        return None


def rewrap_with(session: Session, dek: bytes, new_password: str) -> bool:
    """`rewrap` for a DEK not loaded yet: the recovery reset holds it before
    any session does."""
    row = _row(session)
    if row is None:
        return False
    salt = crypto.new_salt()
    row.kdf_salt = salt
    row.wrapped_dek = crypto.wrap_dek(dek, new_password, salt)
    return True


# The link-reason column decrypts on load; it asks this module for the key
# through a hook rather than an import, which would be a cycle.
LinkReason.key_source = staticmethod(key)
