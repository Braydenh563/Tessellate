"""The words typed but not yet saved, kept sealed across a lock (INBOX 1747, row 22).

Locking empties every field the person was typing in (`purgeLockedContent`,
app.js). Rather than lose a half-written note, the page hands the typed fields
here just before it locks: they are sealed with the vault key into one file in
the data folder and handed back after the next unlock. While locked the file is
ciphertext and this router answers 401 like every other, so the words are no
more readable than a private note.

One file, replaced on each lock: a stale set from an earlier lock never comes
back over a newer one. Nothing here is a note; it never reaches search or the
graph.
"""

from __future__ import annotations

import json
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from tessellate.core import crypto, vault
from tessellate.core.config import ConfigManager
from tessellate.core.deps import get_config

router = APIRouter(prefix="/kept-words", tags=["kept-words"])

FILE = "kept-words.enc"
#: Field count and total text kept: a lock must never be a way to fill the disk.
MAX_FIELDS = 80
MAX_CHARS = 400_000


class KeptWordsIn(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict, max_length=MAX_FIELDS)


def _path(config: ConfigManager):  # noqa: ANN202
    return config.data_dir / FILE


@router.put("")
def keep(body: KeptWordsIn, config: ConfigManager = Depends(get_config)) -> dict:
    """Seal the typed fields. 409 when there is no key to seal with (sign-in off:
    nothing is private then, and the page keeps the words where they are)."""
    dek = vault.key()
    if dek is None:
        raise HTTPException(status_code=409, detail="Unlock first.")
    fields = {k[:80]: v for k, v in body.fields.items() if v}
    if sum(len(v) for v in fields.values()) > MAX_CHARS:
        raise HTTPException(status_code=413, detail="Too much typed text to keep.")
    path = _path(config)
    if not fields:
        path.unlink(missing_ok=True)
        return {"kept": 0}
    sealed = crypto.encrypt(dek, json.dumps({"fields": fields, "at": time.time()}))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(sealed, encoding="utf-8")
    os.replace(tmp, path)
    return {"kept": len(fields)}


@router.get("")
def read(config: ConfigManager = Depends(get_config)) -> dict:
    """The kept fields, or none. An unreadable file (another key) reads as none."""
    dek = vault.key()
    path = _path(config)
    if dek is None or not path.exists():
        return {"fields": {}, "at": None}
    try:
        data = json.loads(crypto.decrypt(dek, path.read_text(encoding="utf-8")))
    except (crypto.DecryptionError, ValueError, OSError):
        return {"fields": {}, "at": None}
    return {"fields": data.get("fields", {}), "at": data.get("at")}


@router.delete("", status_code=204)
def forget(config: ConfigManager = Depends(get_config)) -> Response:
    _path(config).unlink(missing_ok=True)
    return Response(status_code=204)
