"""Signs a release installer for the in-app updater (INBOX 1500).

Writes `<installer>.sig`: Ed25519 over the raw 32-byte SHA-256 of the file,
which is what `core/update_verify.py` checks against its pinned keys. The
private key is the hex seed in the `UPDATE_SIGNING_KEY` environment variable
(a repository secret in the release workflow); it is never an argument, so it
never reaches a process list or a log.

    python packaging/sign_release.py dist/installer/Tessellate-Setup-1.2.3.exe

A missing or malformed key stops the release: installs that pin the key
refuse an unsigned update, so shipping one would strand them.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def sign(path: Path, seed_hex: str) -> Path:
    """Writes `<path>.sig` and returns its path."""
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex.strip()))
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    out = path.with_name(path.name + ".sig")
    out.write_bytes(key.sign(digest.digest()))
    return out


def main(argv: list[str]) -> int:
    seed = os.environ.get("UPDATE_SIGNING_KEY", "")
    if not seed.strip():
        print("::error::UPDATE_SIGNING_KEY is not set, so the installer cannot be signed", file=sys.stderr)
        return 1
    if not argv:
        print("::error::no installer to sign", file=sys.stderr)
        return 1
    for name in argv:
        try:
            print(f"signed {sign(Path(name), seed).name}")
        except ValueError:
            print("::error::UPDATE_SIGNING_KEY is not a 64-character hex Ed25519 seed", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
