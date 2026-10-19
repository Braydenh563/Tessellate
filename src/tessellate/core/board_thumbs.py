"""Board thumbnails: one small WebP or JPEG per board, kept as a file.

The client renders the board to a ~480px image when edits settle and PUTs it;
the file name carries the board id, the fingerprint it was drawn at and the
type, so a path is built from integers and a fixed alphabet and never from
request text. Only the newest thumbnail per board is kept.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

#: A thumbnail is meant to be ~20 KB; 64 KB is the ceiling a client may send.
MAX_BYTES = 64 * 1024
_FP = re.compile(r"^[0-9a-f]{16}$")
_EXT = {"image/webp": "webp", "image/jpeg": "jpg"}
_MIME = {v: k for k, v in _EXT.items()}


def thumb_dir(data_dir: Path) -> Path:
    return data_dir / "board-thumbs"


def fingerprint_hash(parts: tuple) -> str:
    """A stable 16-hex digest of a preview fingerprint (no database identity)."""
    return hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()[:16]


def valid_fp(fp: str) -> bool:
    return bool(_FP.match(fp or ""))


def sniff(data: bytes) -> str | None:
    """The mime type by magic bytes, or None; the declared type is never trusted."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return None


def save(data_dir: Path, board_id: int, fp: str, mime: str, data: bytes) -> None:
    folder = thumb_dir(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{int(board_id)}-{fp}.{_EXT[mime]}"
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    for old in folder.glob(f"{int(board_id)}-*"):
        if old != target:
            old.unlink(missing_ok=True)


def find(data_dir: Path, board_id: int) -> tuple[Path, str, str] | None:
    """`(path, fingerprint, mime)` of the stored thumbnail, if any."""
    for path in thumb_dir(data_dir).glob(f"{int(board_id)}-*"):
        stem, _, ext = path.name.rpartition(".")
        fp = stem.partition("-")[2]
        if ext in _MIME and valid_fp(fp):
            return path, fp, _MIME[ext]
    return None


def stored_fp(data_dir: Path, board_id: int) -> str | None:
    found = find(data_dir, board_id)
    return found[1] if found else None


def forget(data_dir: Path, board_ids: list[int]) -> None:
    for board_id in board_ids:
        try:
            for path in thumb_dir(data_dir).glob(f"{int(board_id)}-*"):
                path.unlink(missing_ok=True)
        except OSError as exc:
            logging.getLogger("tessellate.whiteboard").warning(
                "couldn't remove the thumbnail for board %s (%s)", board_id, type(exc).__name__
            )
