"""The GIF writer behind the ink replay's GIF export (`whiteboard-gif.js`). Run in node; the file it makes is parsed and its
LZW decoded here, in Python, so the encoder is checked against an independent reader."""

from __future__ import annotations

import json
import random
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _encode(width, height, frames, **extra):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    args = json.dumps({"width": width, "height": height, "frames": frames, **extra})
    script = (
        "const wbFmtState = {};\n" + frontend_text("whiteboard-gif.js")
        + f"\nconst a = {args}; a.frames = a.frames.map((f) => Uint8ClampedArray.from(f));"
        + "\nconsole.log(JSON.stringify([...wbFmtState.gif.encode(a)]));"
    )
    return bytes(json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=True).stdout))


def _lzw_decode(data: bytes, min_size: int) -> list[int]:
    clear, end = 1 << min_size, (1 << min_size) + 1
    size, nxt = min_size + 1, end + 1
    table = {i: [i] for i in range(clear)}
    out, prev, acc, bits = [], None, 0, 0
    for byte in data:
        acc |= byte << bits
        bits += 8
        while bits >= size:
            code, acc, bits = acc & ((1 << size) - 1), acc >> size, bits - size
            if code == clear:
                table = {i: [i] for i in range(clear)}
                size, nxt, prev = min_size + 1, end + 1, None
                continue
            if code == end:
                return out
            entry = table[code] if code in table else table[prev] + [table[prev][0]]
            out += entry
            if prev is not None:
                table[nxt] = table[prev] + [entry[0]]
                nxt += 1
                if nxt == (1 << size) and size < 12:
                    size += 1
            prev = code
    return out


def _parse(gif: bytes):
    assert gif[:6] == b"GIF89a"
    width, height = gif[6] | gif[7] << 8, gif[8] | gif[9] << 8
    palette = [tuple(gif[13 + i * 3 : 16 + i * 3]) for i in range(256)]
    pos, frames, delays = 13 + 768, [], []
    while gif[pos] != 0x3B:
        if gif[pos] == 0x21:
            label = gif[pos + 1]
            if label == 0xF9:
                delays.append(gif[pos + 4] | gif[pos + 5] << 8)
            pos += 2
            while gif[pos]:
                pos += gif[pos] + 1
            pos += 1
        else:
            assert gif[pos] == 0x2C
            pos += 10
            min_size, pos, blob = gif[pos], pos + 1, b""
            while gif[pos]:
                blob += gif[pos + 1 : pos + 1 + gif[pos]]
                pos += gif[pos] + 1
            pos += 1
            frames.append(_lzw_decode(blob, min_size))
    return width, height, palette, frames, delays


def _solid(width, height, rgb):
    return [c for _ in range(width * height) for c in (*rgb, 255)]


def test_two_frames_make_a_valid_gif_with_the_right_size_count_and_delays():
    gif = _encode(4, 3, [_solid(4, 3, (255, 255, 255)), _solid(4, 3, (255, 0, 0))], delay=10, hold=99)
    width, height, _palette, frames, delays = _parse(gif)
    assert (width, height, len(frames), delays) == (4, 3, 2, [10, 99])
    assert gif.endswith(b"\x3b") and b"NETSCAPE2.0" in gif


def test_pixels_come_back_as_their_palette_colours():
    colours = [(255, 255, 255), (255, 0, 0), (0, 0, 0), (51, 102, 204), (128, 128, 128)]
    pixels = [c for rgb in colours for c in (*rgb, 255)]
    width, _h, palette, frames, _d = _parse(_encode(5, 1, [pixels]))
    got = [palette[i] for i in frames[0]]
    for want, have in zip(colours, got):
        assert all(abs(a - b) <= 26 for a, b in zip(want, have)), (want, have)
    assert got[0] == (255, 255, 255) and got[1] == (255, 0, 0) and got[2] == (0, 0, 0)


def test_a_noisy_frame_that_fills_the_code_table_still_round_trips():
    rng = random.Random(3)
    side = 64
    pixels = [c for _ in range(side * side) for c in (rng.randrange(256), rng.randrange(256), rng.randrange(256), 255)]
    _w, _h, palette, frames, _d = _parse(_encode(side, side, [pixels]))
    assert len(frames[0]) == side * side
    first = [palette[i] for i in frames[0][:200]]
    for i, have in enumerate(first):
        assert all(abs(pixels[i * 4 + k] - have[k]) <= 60 for k in range(3))


def test_a_transparent_pixel_is_the_white_ground():
    _w, _h, palette, frames, _d = _parse(_encode(2, 1, [[0, 0, 0, 0, 10, 20, 30, 0]]))
    assert [palette[i] for i in frames[0]] == [(255, 255, 255), (255, 255, 255)]


def test_the_writer_is_lazy_loaded_with_the_board():
    assert "/js/whiteboard-gif.js" in frontend_text("lazy-entries.js")
