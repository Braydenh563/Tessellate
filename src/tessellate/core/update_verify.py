"""Checks a downloaded installer before it is run (audit 1031 BK6; 1028 K5).

The in-app update downloads an executable and starts it. Until now the only
checks were the host it came from and that it was not cut short. Two more:

* **The digest.** GitHub lists a `sha256:` digest for every release asset in
  the same API answer that names the asset. The download must match it, so a
  file swapped in transit, or by a CDN, is refused.
* **A detached signature, once a key is pinned.** `PUBLIC_KEYS` holds Ed25519
  public keys (64 hex characters each). While it is empty the digest alone is
  the check. Once the owner pins a key, a release without a `<installer>.sig`
  asset that verifies under one of the keys is refused: the signature is
  Ed25519 over the raw 32-byte SHA-256 of the installer, which is what lets a
  release step sign a hash instead of a 150 MB file. Several keys are allowed
  so one can be rotated without stranding the installs that carry the old one.

Every refusal is a sentence for the person; the reason never carries a path.
"""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

#: Pinned release-signing keys (hex Ed25519 public keys). Empty until the
#: owner generates a pair and adds the signing step to the release workflow;
#: see INBOX 1500.
PUBLIC_KEYS: tuple[str, ...] = ()

CHUNK = 1 << 20
UNCHECKABLE = "The update could not be checked, so it was not installed. Download it from the releases page instead."
MISMATCH = "The downloaded installer does not match the one that was published, so it was not installed."
UNSIGNED = "The update's signature could not be verified, so it was not installed."


def _sha256(path: Path) -> bytes:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.digest()


def _listed(digest: object) -> bytes | None:
    """The 32 bytes of a `sha256:<hex>` digest, or None when it is anything else."""
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return None
    try:
        raw = bytes.fromhex(digest[7:])
    except ValueError:
        return None
    return raw if len(raw) == 32 else None


def _accepts(key: Ed25519PublicKey, signature: bytes, message: bytes) -> bool:
    try:
        key.verify(signature, message)
        return True
    except InvalidSignature:
        return False


def _signed_by_any(keys: tuple[str, ...], signature: bytes, message: bytes) -> bool:
    for hex_key in keys:
        try:
            key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_key))
        except ValueError:
            continue
        #: A small-order key (the all-zero one is the plain case) accepts an
        #: all-zero "signature" for any message, so anyone could forge one. A
        #: real key never accepts it: probe, and ignore a key that does.
        if _accepts(key, bytes(64), message) or _accepts(key, bytes(64), b"probe"):
            continue
        if _accepts(key, signature, message):
            return True
    return False


def refusal(path: Path, *, digest: object, signature: bytes | None, keys: tuple[str, ...] | None = None) -> str | None:
    """Why this installer must not run, or None when it may."""
    pinned = PUBLIC_KEYS if keys is None else keys
    actual = _sha256(path)
    listed = _listed(digest)
    if listed is not None and not hmac.compare_digest(listed, actual):
        return MISMATCH
    if pinned:
        if signature is None or not _signed_by_any(pinned, signature, actual):
            return UNSIGNED
        return None
    return None if listed is not None else UNCHECKABLE
