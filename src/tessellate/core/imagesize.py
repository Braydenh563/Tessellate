"""(width, height) of a PNG, GIF, JPEG or WebP from its header, no Pillow.

An answer's figure (INBOX 526) is drawn with the picture's real size so the
page does not jump when it loads. A header read, never a decode: a file that
is none of these, or is cut short, gives None and the figure sizes itself.
"""

from __future__ import annotations

import struct
from pathlib import Path

#: A JPEG's size sits after its EXIF block, which can be large.
_HEAD_BYTES = 262_144


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            head = handle.read(_HEAD_BYTES)
    except OSError:
        return None
    try:
        size = _size(head)
    except (struct.error, IndexError):
        return None
    return size if size and size[0] > 0 and size[1] > 0 else None


def _webp_size(head: bytes) -> tuple[int, int] | None:
    kind = head[12:16]
    if kind == b"VP8X":
        return (int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1)
    if kind == b"VP8 ":
        width, height = struct.unpack("<HH", head[26:30])
        return (width & 0x3FFF, height & 0x3FFF)
    if kind == b"VP8L":
        bits = int.from_bytes(head[21:25], "little")
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    return None


def _jpeg_size(head: bytes) -> tuple[int, int] | None:
    at = 2
    while at + 9 < len(head):
        if head[at] != 0xFF:
            at += 1
            continue
        marker = head[at + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            at += 1 if marker == 0xFF else 2
            continue
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", head[at + 5 : at + 9])
            return (width, height)
        at += 2 + struct.unpack(">H", head[at + 2 : at + 4])[0]
    return None


def _size(head: bytes) -> tuple[int, int] | None:
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", head[16:24])
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", head[6:10])
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return _webp_size(head)
    if head[:2] == b"\xff\xd8":
        return _jpeg_size(head)
    return None
