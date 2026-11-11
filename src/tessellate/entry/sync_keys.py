"""Private notes between paired computers (WORLD_CLASS_PLAN B6, decision 12).

Each notebook encrypts private notes with its own data key. At pairing the
other computer hands its data key over the verified TLS sign-in, which only
its password could open (whoever has the password can already unwrap that
key, so this gives nothing the password did not), and this computer keeps it
wrapped under its own data key in `sync-state.json`, so it is no more
readable at rest than this notebook's own private notes.

On apply, a private note from the other computer is opened with its key and
sealed again with this one's, so every reader here (the list, titles,
History, export) works on it as on any private note; comparisons are made on
the plain text, because the two computers' ciphertexts of the same words
differ. Without both keys (this notebook locked, or paired before this
existed) the note lands as it came, ciphertext only, and says so.
"""

from __future__ import annotations

import base64
from pathlib import Path

from tessellate.core import crypto, sync_state, vault

#: (the other computer's data key, this computer's data key)
Keys = tuple[bytes, bytes]


def wrap_peer_key(encoded: str | None) -> str:
    """The other computer's key (base64, as `/sync/pass` sends it) sealed with this one's; '' when either is missing."""
    own = vault.key()
    if not encoded or own is None:
        return ""
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError:
        return ""
    return crypto.encrypt(own, base64.b64encode(raw).decode()) if len(raw) == len(crypto.new_dek()) else ""


def own_key_for_peer() -> str:
    """This notebook's data key for a signed-in paired computer, base64; '' while it is locked."""
    own = vault.key()
    return base64.b64encode(own).decode() if own is not None else ""


def keys(data_dir: Path) -> Keys | None:
    """Both keys, when this notebook is unlocked and holds the paired computer's."""
    own, wrapped = vault.key(), sync_state.link(data_dir).get("peer_key")
    if own is None or not wrapped:
        return None
    try:
        return base64.b64decode(crypto.decrypt(own, wrapped)), own
    except (crypto.DecryptionError, ValueError):
        return None


def opened(item: dict, both: Keys | None) -> dict:
    """The item with its words in the clear (`plain`) and sealed with this notebook's key."""
    if both is None or not item["is_private"] or not crypto.is_encrypted(item["content"]):
        return item
    try:
        plain = crypto.decrypt(both[0], item["content"])
    except crypto.DecryptionError:
        return item
    return {**item, "plain": plain, "content": crypto.encrypt(both[1], plain)}


def local_plain(content: str, both: Keys | None) -> str | None:
    """This notebook's copy in the clear, to compare with an `opened` item."""
    if both is None or not crypto.is_encrypted(content):
        return content
    try:
        return crypto.decrypt(both[1], content)
    except crypto.DecryptionError:
        return None
