"""A frame the page sends is capped by its pixels before it is decoded (review 1109): 9000 x 9000 is under Pillow's own 89 million bomb limit, so only this cap stops it."""

from __future__ import annotations

import base64
import io
import struct
import zlib

import pytest
from PIL import Image

from tessellate.core.overlay import capture


def _chunk(tag: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))


def _header_only_png(width: int, height: int) -> str:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IEND", b"")
    return base64.b64encode(raw).decode()


def test_a_huge_header_only_png_is_refused_before_it_is_decoded(monkeypatch):
    loaded: list[int] = []
    real = Image.Image.convert

    def watching(self, *a, **k):
        loaded.append(1)
        return real(self, *a, **k)

    monkeypatch.setattr(Image.Image, "convert", watching)
    with pytest.raises(ValueError):
        capture.decode(_header_only_png(9000, 9000))
    assert loaded == []


def test_a_frame_of_the_expected_size_still_decodes():
    buf = io.BytesIO()
    Image.new("RGBA", (560, 600), (1, 2, 3, 255)).save(buf, "PNG")
    im = capture.decode(base64.b64encode(buf.getvalue()).decode())
    assert im.size == (560, 600)
