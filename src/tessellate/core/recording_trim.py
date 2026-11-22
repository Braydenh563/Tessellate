"""Cutting a part out of a recorded wav (ledger L685, D18).

The app has no muxer for webm, ogg or mp4, but it writes and reads the PCM
wav the tab-side trim makes, and the standard library's `wave` can cut one
without decoding it into memory: the header is written for the kept length,
then the kept frames stream across in blocks. The cut keeps the source's
rate, channels and sample width (the same container), and never touches the
source file."""

from __future__ import annotations

import json
import struct
import wave
from collections.abc import Iterator
from pathlib import Path

#: Frames read at a time: a megabyte or so of 16-bit stereo.
BLOCK_FRAMES = 262_144


class NotTrimmable(ValueError):
    """The file is not a PCM wav this module can cut."""


def span(path: Path) -> tuple[int, int, int, int]:
    """`(channels, width, rate, frames)` of a PCM wav, or `NotTrimmable`."""
    try:
        with wave.open(str(path), "rb") as src:
            return src.getnchannels(), src.getsampwidth(), src.getframerate(), src.getnframes()
    except (wave.Error, EOFError) as exc:
        raise NotTrimmable("That recording isn't a plain wav the app can cut.") from exc


def frame_range(rate: int, frames: int, start_ms: int, end_ms: int) -> tuple[int, int]:
    """The kept frames `[first, last)`, clamped to the file."""
    first = min(frames, max(0, start_ms * rate // 1000))
    last = min(frames, max(first, end_ms * rate // 1000))
    return first, last


def header(channels: int, width: int, rate: int, frames: int) -> bytes:
    """The 44-byte header of a PCM wav of `frames` frames."""
    size = frames * channels * width
    return (
        b"RIFF" + struct.pack("<I", 36 + size) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * channels * width, channels * width, width * 8)
        + b"data" + struct.pack("<I", size)
    )


def cut(path: Path, first: int, last: int) -> Iterator[bytes]:
    """The header, then the frames `[first, last)` in blocks."""
    channels, width, rate, _frames = span(path)
    yield header(channels, width, rate, last - first)
    with wave.open(str(path), "rb") as src:
        src.setpos(first)
        left = last - first
        while left > 0:
            block = src.readframes(min(BLOCK_FRAMES, left))
            if not block:
                # The header promised frames the file does not hold.
                raise NotTrimmable("That recording is shorter than its header says.")
            left -= len(block) // (channels * width)
            yield block


def kept_peaks(peaks_json: str, duration_ms: int, start_ms: int, end_ms: int) -> list[float]:
    """The bars of the part kept (the tab's slice, by the same arithmetic)."""
    peaks = json.loads(peaks_json or "[]")
    span_ms = duration_ms or 1
    return peaks[int(start_ms / span_ms * len(peaks)) : -(-end_ms * len(peaks) // span_ms)]


def kept_markers(marks: list[dict], start_ms: int, end_ms: int) -> list[float | dict]:
    """The marks inside the part, moved to count from its start."""
    out: list[float | dict] = []
    for mark in marks:
        if start_ms <= mark["at"] <= end_ms:
            at = mark["at"] - start_ms
            out.append({"at": at, "note": mark["note"]} if mark.get("note") else at)
    return out
