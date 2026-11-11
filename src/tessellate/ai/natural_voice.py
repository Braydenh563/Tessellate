"""A natural voice that reads on this computer (WORLD_CLASS_PLAN rows 35 and 37,
Q34; ANALYSIS "Piper, OHF-Voice/piper1-gpl"): text in, a wav out, nothing sent.

**Optional, never vendored.** The engine is the `piper-tts` wheel (GPL-3.0, which
combines into this AGPL-3.0 app; a pip extra, `naturalvoice`) and the voice is two
pinned files (`naturalvoice-voice`, public-domain LJ Speech data), both fetched on an
Install click in Settings, Packages. Without them the browser's own voices keep
reading aloud (`media.js speakText`); nothing here is needed to start the app and no
test needs a real engine (`TESSELLATE_PIPER_VOICE` names one for the one real-engine
check).

**Sentence by sentence.** A script is spoken one sentence at a time so the transcript
of the audio is exact: each sentence's start and end in the wav are the cumulative
length of what came before, plus a short pause. That is what a saved overview keeps
as its transcript lines, so a line seeks the audio like any recording's.
"""

from __future__ import annotations

import importlib.util
import io
import logging
import os
import re
import threading
import wave
from collections.abc import Callable
from pathlib import Path

from tessellate.core import extras

logger = logging.getLogger("tessellate.natural_voice")

ENGINE_ID = "naturalvoice"
VOICE_ID = "naturalvoice-voice"
VOICE_FILE = "en_US-ljspeech-medium.onnx"
VOICE_CONFIG = VOICE_FILE + ".json"
#: Silence after each sentence, so the speech breathes.
PAUSE_MS = 350
#: One read-aloud request: a long note, not a book. The page sends a message or a selection.
MAX_CHARS = 12_000
#: A sentence longer than this is cut at a clause so one call never runs for minutes.
MAX_SENTENCE = 400

INSTALL_HINT = (
    "A natural voice needs the Natural voice package: Settings, Packages, Install on Natural voice. "
    "Until then your browser's own voices read aloud."
)

_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]*[A-Z0-9])")
_CLAUSE = re.compile(r"(?<=[,;:])\s+")
_MARKUP = re.compile(r"[`*_#>|~]+|\[\[|\]\]|!?\[([^\]]*)\]\([^)]*\)")

_lock = threading.Lock()
_loaded: tuple[Path, object] | None = None


class Stopped(RuntimeError):
    """Raised inside `render` when the caller asked it to stop."""


def voice_dir() -> Path | None:
    """The folder holding the installed voice, or None. A look at the disk."""
    return extras.download_ready(VOICE_ID)


def model_path() -> Path | None:
    override = os.environ.get("TESSELLATE_PIPER_VOICE", "").strip()
    if override and Path(override).is_file():
        return Path(override)
    folder = voice_dir()
    return folder / VOICE_FILE if folder else None


def engine_installed() -> bool:
    return importlib.util.find_spec("piper") is not None


def available() -> bool:
    return engine_installed() and model_path() is not None


def status() -> dict:
    """What `/voice/status` says: ready, or which half is missing."""
    engine, voice = engine_installed(), model_path() is not None
    return {
        "available": engine and voice,
        "engine": engine,
        "voice": voice,
        "name": "LJ Speech, US English",
        "hint": None if engine and voice else INSTALL_HINT,
    }


def plain(text: str) -> str:
    """Text as it is spoken: markdown marks and link addresses dropped, spaces folded."""
    spoken = _MARKUP.sub(lambda m: m.group(1) or "", text or "")
    return " ".join(spoken.split())


def sentences(text: str) -> list[str]:
    """The text as sentences, each short enough to speak in one call."""
    out: list[str] = []
    for part in _SENTENCE_END.split(plain(text)):
        part = part.strip()
        while len(part) > MAX_SENTENCE:
            cut = _clause_cut(part)
            out.append(part[:cut].strip())
            part = part[cut:].strip()
        if part:
            out.append(part)
    return out


def _clause_cut(part: str) -> int:
    """Where to cut a long sentence: the last clause break before the limit, else a space."""
    head = part[:MAX_SENTENCE]
    breaks = [m.end() for m in _CLAUSE.finditer(head)]
    if breaks:
        return breaks[-1]
    return head.rfind(" ") + 1 or MAX_SENTENCE


def _load() -> object:
    """The voice, loaded once (a few seconds the first time) and kept."""
    global _loaded
    path = model_path()
    if path is None or not engine_installed():
        raise RuntimeError(INSTALL_HINT)
    with _lock:
        if _loaded is None or _loaded[0] != path:
            from piper import PiperVoice  # the optional engine; imported only when it speaks

            _loaded = (path, PiperVoice.load(path))
        return _loaded[1]


def _pcm(voice: object, sentence: str) -> bytes:
    """16-bit mono samples of one sentence."""
    return b"".join(chunk.audio_int16_bytes for chunk in voice.synthesize(sentence))  # type: ignore[attr-defined]


def render(
    lines: list[str],
    *,
    should_stop: Callable[[], bool] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[bytes, list[dict]]:
    """A wav of the lines and the transcript segments (`start`, `end`, `text` in
    milliseconds) that match it. Raises `Stopped` between sentences when asked."""
    voice = _load()
    rate = int(voice.config.sample_rate)  # type: ignore[attr-defined]
    pause = b"\x00\x00" * (rate * PAUSE_MS // 1000)
    pcm, segments, at = [], [], 0
    for index, line in enumerate(lines):
        if should_stop is not None and should_stop():
            raise Stopped("stopped")
        data = _pcm(voice, line)
        length = len(data) // 2 * 1000 // rate
        segments.append({"start": at, "end": at + length, "text": line})
        pcm += [data, pause]
        at += length + PAUSE_MS
        if progress is not None:
            progress(index + 1, len(lines))
    return _wav(b"".join(pcm), rate), segments


def _wav(pcm: bytes, rate: int) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(pcm)
    return out.getvalue()


def speak(text: str) -> bytes:
    """A wav of `text` (at most `MAX_CHARS`); `ValueError` when there is nothing to say."""
    lines = sentences((text or "")[:MAX_CHARS])
    if not lines:
        raise ValueError("There is nothing to read.")
    return render(lines)[0]


def release() -> None:
    """Drop the loaded voice, so a reinstall or a removal can replace its file."""
    global _loaded
    with _lock:
        _loaded = None


reset_for_tests = release


#: A reinstall or removal of the voice replaces a file the loaded voice holds open (Windows cannot).
extras.on_release(extras.VOICE_IDS, release)
