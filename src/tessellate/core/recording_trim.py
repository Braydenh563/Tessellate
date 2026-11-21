"""Cut a span out of a recording on the server (L632).

The page used to decode the whole take with the Web Audio API (about 12 MB a
minute of memory) to write the part kept. Here PyAV (the voice add-on's
decoder) reads the file packet by packet and only the span is kept, mixed to
one channel as 16-bit wav. A wav needs no decoder at all: with PyAV missing it
is cut with the standard library; any other container asks for the add-on.
"""

from __future__ import annotations

import importlib.util
import io
import wave
from pathlib import Path

NEEDS_ADDON = "Trimming this recording needs the voice add-on's audio reader. Install it in Settings, Packages, then try again."


class TrimError(RuntimeError):
    """The cut could not be made; the message is a sentence for the person."""


def available() -> bool:
    return importlib.util.find_spec("av") is not None


def _wav_bytes(rate: int, samples: bytes) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(samples)
    return out.getvalue()


def _cut_wav(path: Path, start_ms: int, end_ms: int) -> bytes:
    """A 16-bit wav cut with `wave`, one channel kept (the first, or the mean for two)."""
    import array

    try:
        with wave.open(str(path)) as audio:
            rate, width, channels = audio.getframerate(), audio.getsampwidth(), audio.getnchannels()
            if width != 2:
                raise TrimError(NEEDS_ADDON)
            first = min(audio.getnframes(), start_ms * rate // 1000)
            audio.setpos(first)
            data = audio.readframes(max(0, end_ms * rate // 1000 - first))
    except (wave.Error, EOFError) as exc:
        raise TrimError("That recording's audio couldn't be read.") from exc
    samples = array.array("h")
    samples.frombytes(data[: len(data) // 2 * 2])
    if channels > 1:
        samples = array.array("h", (sum(samples[i : i + channels]) // channels for i in range(0, len(samples) - channels + 1, channels)))
    return _wav_bytes(rate, samples.tobytes())


def _cut_av(path: Path, start_ms: int, end_ms: int) -> bytes:
    import av

    chunks: list[bytes] = []
    rate = 0
    try:
        with av.open(str(path), mode="r") as container:
            stream = container.streams.audio[0]
            rate = stream.rate or stream.codec_context.sample_rate
            resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
            #: Seek to the span's start (a keyframe before it), then drop what
            #: precedes it frame by frame; stop at the end, never decode past it.
            if start_ms > 0:
                container.seek(int(start_ms * 1000), any_frame=False, backward=True)
            want_from, want_to = start_ms * rate // 1000, end_ms * rate // 1000
            pos = 0  #: absolute sample index of the next frame
            for frame in container.decode(stream):
                if frame.time is not None:
                    pos = round(float(frame.time) * rate)
                if pos >= want_to:
                    break
                for out in resampler.resample(frame):
                    chunk = out.to_ndarray().reshape(-1)
                    part = chunk[max(0, want_from - pos) : max(0, want_to - pos)]
                    if len(part):
                        chunks.append(part.tobytes())
                    pos += len(chunk)
    except (av.error.FFmpegError, IndexError, ValueError) as exc:
        raise TrimError("That recording's audio couldn't be read.") from exc
    return _wav_bytes(rate or 16000, b"".join(chunks))


def cut(path: Path, start_ms: int, end_ms: int) -> bytes:
    """The audio of `path` from `start_ms` to `end_ms`, as a mono 16-bit wav."""
    if end_ms <= start_ms:
        raise TrimError("The end must come after the start.")
    if available():
        return _cut_av(path, start_ms, end_ms)
    if path.suffix.lower() == ".wav":
        return _cut_wav(path, start_ms, end_ms)
    raise TrimError(NEEDS_ADDON)
