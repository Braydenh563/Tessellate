"""Every input has a bound at the model (audit 1029 H10, X26, N18, G27).

One place for the limits a request body or upload is held to, so a new field
reaches for a name here instead of choosing its own number (or none).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import HTTPException
from pydantic import Field

#: A stored display name (an attachment, a media upload): long enough for any
#: real filename, short enough to be a readable row and an aria-label.
NAME_MAX = 120

#: Prior chat turns a request may carry. The page sends at most five
#: (`MAX_CLIENT_HISTORY`, capture-ask.js); the server clips again to fit the
#: model, so this only stops a body that is a payload rather than a history.
HISTORY_MAX_TURNS = 40
#: One side of one turn. An answer can be long; 600 MB of them cannot be a chat.
TURN_TEXT_MAX = 50_000

#: Steps in one batch undo (a change to several notes or board items).
BATCH_STEPS_MAX = 200
#: The edited text of an attached file, in characters: the upload cap
#: (`MAX_FILE_BYTES`, 50 MB) is the most a file can hold, so the same figure.
FILE_TEXT_MAX = 50 * 1024 * 1024
#: The same file as base64 (4 characters for every 3 bytes) for the save route.
FILE_BASE64_MAX = FILE_TEXT_MAX * 4 // 3 + 4
#: A persona, response mode, tool or skill-input name or value.
LABEL_MAX = 80

#: A graph position. The map is a few thousand units across; a pin outside
#: this range is not a place, and 1e308 breaks the camera fit.
PIN_LIMIT = 1_000_000.0
PinCoord = Annotated[float, Field(ge=-PIN_LIMIT, le=PIN_LIMIT, allow_inf_nan=False)]

def display_name(raw: str | None, fallback: str) -> str:
    """The name to keep for an upload: no folders, no control characters, at
    most `NAME_MAX` characters with the extension kept."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    if not name or name in {".", ".."}:
        return fallback[:NAME_MAX]
    if len(name) <= NAME_MAX:
        return name
    stem, dot, suffix = name.rpartition(".")
    if not dot or len(suffix) > 12:
        return name[:NAME_MAX]
    return stem[: NAME_MAX - len(suffix) - 1] + "." + suffix


def check_image_upload(head: bytes, size: int) -> None:
    """Refuse an empty upload and markup named like a picture. Anything else
    passes: the suffix allowlist and `nosniff` already decide what is served."""
    if size <= 0:
        raise HTTPException(status_code=422, detail="That file is empty.")
    if head.lstrip()[:1] == b"<":
        raise HTTPException(status_code=415, detail="That file is not an image or PDF.")
