"""Windows Hello unlock: a third wrap of the vault key (INBOX 1727).

Beside the password's wrap (core/vault.py) and the PIN's (core/pinstore.py),
this one is opened by the WebAuthn PRF extension: the platform authenticator
(Windows Hello's TPM key) turns a fixed salt into 32 secret bytes only after
the person's face, finger or Windows PIN. Those bytes, through HKDF, are the
AES-GCM key around the vault's data key. So Hello is never a yes-or-no gate
in front of a key kept in the clear: without the authenticator's answer the
record is ciphertext, and a stolen notebook or record opens nothing.

The PIN's rules carry over unchanged:

- **The record lives in the OS protected store**, through `pinstore.store()`
  under its own account name, never in the notebook, its data dir or a
  backup.
- **It is bound** (`pinstore.binding`) to the vault row and password hash it
  was made against, so a password change, a re-key or a restore leaves it
  unable to open anything; those paths `forget` it beside the PIN.
- **This computer only**: the routes refuse every other device, as for the PIN.

The record also keeps the credential id and public key, so the server checks
the assertion's signature (core/webauthn.py) before it tries the unwrap.
Challenges are single use and expire after `CHALLENGE_SECONDS`.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from tessellate.core import crypto, pinstore

log = logging.getLogger("tessellate.hello")

_AAD_PREFIX = b"tessellate-hello-v1|"
_HKDF_INFO = b"tessellate-hello-v1 vault wrap"
CHALLENGE_SECONDS = 120
#: Pending challenges at most: `begin` needs no session, so the table is capped.
_MAX_PENDING = 16
PRF_BYTES = 32


def _account(data_dir: Path) -> str:
    return pinstore.account_for(data_dir) + "-hello"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _read(data_dir: Path) -> dict | None:
    raw = pinstore.store(data_dir).get(_account(data_dir))
    if not raw:
        return None
    try:
        record = json.loads(base64.b64decode(raw, validate=True))
    except (ValueError, TypeError):
        return None
    return record if isinstance(record, dict) and record.get("v") == 1 else None


def _write(data_dir: Path, record: dict) -> None:
    pinstore.store(data_dir).put(_account(data_dir), _b64(json.dumps(record).encode()))


def _wrap_key(prf: bytes) -> bytes:
    if len(prf) != PRF_BYTES:
        raise ValueError("a PRF output is 32 bytes")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(prf)


def available(data_dir: Path) -> bool:
    return pinstore.available(data_dir)


def record(data_dir: Path) -> dict | None:
    """This notebook's Hello record on this computer, or None."""
    if not available(data_dir):
        return None
    try:
        return _read(data_dir)
    except pinstore.StoreError:
        return None


def is_set(data_dir: Path) -> bool:
    return record(data_dir) is not None


def save(
    data_dir: Path, *, credential_id: bytes, rp_id: str, alg: int, spki: bytes,
    sign_count: int, prf_salt: bytes, prf: bytes, dek: bytes, bound_to: bytes,
) -> None:
    """Wrap `dek` under the PRF output into the OS store. Raises StoreError."""
    if not available(data_dir):
        raise pinstore.StoreError("no protected store on this computer")
    nonce = os.urandom(crypto.NONCE_BYTES)
    sealed = AESGCM(_wrap_key(prf)).encrypt(nonce, dek, _AAD_PREFIX + bound_to + credential_id)
    made = {
        "v": 1,
        "cred": _b64(credential_id),
        "rp": rp_id,
        "alg": alg,
        "spki": _b64(spki),
        "count": int(sign_count),
        "salt": _b64(prf_salt),
        "nonce": _b64(nonce),
        "ct": _b64(sealed),
    }
    with _lock:
        _write(data_dir, made)
        if _read(data_dir) != made:
            forget(data_dir)
            raise pinstore.StoreError("the protected store did not keep the Hello record")


def unwrap(data_dir: Path, made: dict, prf: bytes, bound_to: bytes) -> bytes | None:
    """The data key, or None when the PRF output or the binding is wrong."""
    try:
        nonce = base64.b64decode(made["nonce"])
        sealed = base64.b64decode(made["ct"])
        cred = base64.b64decode(made["cred"])
        return AESGCM(_wrap_key(prf)).decrypt(nonce, sealed, _AAD_PREFIX + bound_to + cred)
    except (InvalidTag, KeyError, ValueError, TypeError):
        return None


def note_sign_count(data_dir: Path, count: int) -> None:
    """Keep the authenticator's latest count (clone detection), if it keeps one."""
    with _lock:
        made = _read(data_dir)
        if made is None or not count or made.get("count") == count:
            return
        made["count"] = int(count)
        try:
            _write(data_dir, made)
        except pinstore.StoreError:
            log.warning("could not keep the Hello sign count", exc_info=True)


def forget(data_dir: Path) -> bool:
    """Remove this notebook's Hello record. True when one was there."""
    try:
        if not available(data_dir):
            return False
        had = _read(data_dir) is not None
        pinstore.store(data_dir).delete(_account(data_dir))
        return had
    except pinstore.StoreError:
        log.warning("could not remove the Hello record from the protected store", exc_info=True)
        return False


# --- challenges -----------------------------------------------------------------

_lock = threading.Lock()
#: ticket -> (kind, challenge, expires, extra)
_pending: dict[str, tuple[str, bytes, float, dict]] = {}


def _now() -> float:
    """Monotonic seconds; a test replaces this to step past the expiry."""
    return time.monotonic()


def issue(kind: str, extra: dict | None = None) -> tuple[str, bytes]:
    """A fresh (ticket, challenge) for one ceremony of `kind`."""
    now = _now()
    with _lock:
        for ticket in [t for t, (_, _, until, _) in _pending.items() if until <= now]:
            _pending.pop(ticket, None)
        while len(_pending) >= _MAX_PENDING:
            _pending.pop(next(iter(_pending)))
        ticket, challenge = secrets.token_urlsafe(18), secrets.token_bytes(32)
        _pending[ticket] = (kind, challenge, now + CHALLENGE_SECONDS, dict(extra or {}))
    return ticket, challenge


def take(ticket: str, kind: str) -> tuple[bytes, dict] | None:
    """The challenge for `ticket`, once: spent whether or not it then verifies."""
    with _lock:
        held = _pending.pop(ticket or "", None)
    if held is None:
        return None
    held_kind, challenge, until, extra = held
    if held_kind != kind or until <= _now():
        return None
    return challenge, extra


def reset_for_tests() -> None:
    with _lock:
        _pending.clear()
