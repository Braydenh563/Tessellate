"""Local speech-to-text: optional, like everything AI here.

Uses faster-whisper (Whisper running on CPU via CTranslate2) when the
user has installed it:  pip install faster-whisper
Nothing else in the app depends on it: without the package the voice
endpoints report "not available" with that hint, and the mic button in
the UI explains instead of breaking. Audio never leaves the machine.
"""

from __future__ import annotations

import importlib.util
import logging
import threading
from collections.abc import Iterator
from pathlib import Path

from tessellate.core.logbuffer import safe_value

#: Names the add-on as Settings, Packages lists it ("Voice notes"), not the
#: command that installs it: the person reads this in a toast.
INSTALL_HINT = (
    "Voice notes need an add-on that isn't installed yet. Install “Voice "
    "notes” in Settings, Packages, then restart the app."
)

logger = logging.getLogger(__name__)

# One loaded model per process; Whisper models are too heavy to reload
# per request. Guarded by a lock because two requests can race the load.
#
# The size and the model are one cache entry, not two globals: kept apart, the
# pair can be written half-way, the old model still loaded under the new
# size's name: and every later call then hands back the wrong model believing
# it is the right one. A single tuple cannot get out of step with itself.
_loaded: tuple[str, object] | None = None
_lock = threading.Lock()


#: Whisper's options from Settings (Brief 87 step 2; ANALYSIS.md "Vendor
#: candidates, 2026-10-11", rows 1 and 10). Silence skipping is Silero VAD,
#: which faster-whisper already carries, so it costs no download: Whisper fed
#: the hum before and after a clip writes words nobody said. The language and
#: the words to expect are off until set; detection and no prompt are
#: faster-whisper's own defaults.
LANGUAGES = ("en", "es", "fr", "de", "it", "pt", "nl", "pl", "sv", "da", "no", "fi", "ru", "uk", "tr", "ar", "hi", "ja", "zh", "ko")
#: Whisper reads at most 224 tokens of prompt; a few names and terms is the use.
VOCABULARY_MAX = 200


def options_from(config) -> dict:  # noqa: ANN001  # a ConfigManager
    """`model.transcribe` keyword arguments from the three preferences."""
    options: dict = {}
    if config.get_preference("voice_skip_silence", True):
        options["vad_filter"] = True
    language = str(config.get_preference("voice_language", "") or "").strip().lower()
    if language in LANGUAGES:
        options["language"] = language
    words = " ".join(str(config.get_preference("voice_vocabulary", "") or "").split())
    if words:
        options["initial_prompt"] = words[:VOCABULARY_MAX]
    return options


#: `core/deps.peek_config`, set by deps when it loads (deps imports this
#: module's neighbours, so importing it here would be a cycle).
CONFIG_PEEK = lambda: None  # noqa: E731


def _options() -> dict:
    """The running app's options; none outside it (a script, a bare test).
    `peek_config`, never `get_config`: that one makes a data folder."""
    config = CONFIG_PEEK()
    return options_from(config) if config is not None else {}


def whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


#: The sizes Settings offers, with what each download weighs (the model.bin of
#: the Systran conversions faster-whisper fetches on first use). The repo is
#: never anything a request supplies: a size is an allowlist key.
WHISPER_SIZES = {
    "tiny": ("Systran/faster-whisper-tiny", "~75 MB"),
    "base": ("Systran/faster-whisper-base", "~145 MB"),
    "small": ("Systran/faster-whisper-small", "~485 MB"),
    "medium": ("Systran/faster-whisper-medium", "~1.5 GB"),
}


def _whisper_dir(size: str) -> Path:
    from tessellate.core.embedmodels import cache_root

    return cache_root() / ("models--" + WHISPER_SIZES[size][0].replace("/", "--"))


def _dir_bytes(folder: Path) -> int:
    #: The snapshot's files are symlinks to `blobs/`; counting both would
    #: weigh every model twice.
    return sum(
        path.stat().st_size for path in folder.rglob("*") if path.is_file() and not path.is_symlink()
    )


def model_states() -> dict[str, dict]:
    """Which sizes are on this computer. Installed means a snapshot holds the
    weights and the config, not just the folder an interrupted first dictation
    leaves behind."""
    out: dict[str, dict] = {}
    for size, (_repo, approx) in WHISPER_SIZES.items():
        folder = _whisper_dir(size)
        ready = False
        if folder.is_dir():
            for snapshot in (folder / "snapshots").glob("*"):
                if (snapshot / "model.bin").exists() and (snapshot / "config.json").exists():
                    ready = True
                    break
        out[size] = {"installed": ready, "bytes": _dir_bytes(folder) if ready else 0, "approx": approx}
    return out


def remove_model(size: str) -> tuple[bool, str]:
    """Delete one downloaded size from the cache. Removing is a re-download,
    nothing more, so it says that rather than warning of loss. The folder is
    checked to sit inside the cache root before anything goes."""
    global _loaded
    if size not in WHISPER_SIZES:
        return False, "No such dictation model."
    from tessellate.core.embedmodels import cache_root

    folder = _whisper_dir(size)
    if not folder.is_dir():
        return False, f"The {size} dictation model isn't on this computer."
    if not folder.resolve().is_relative_to(cache_root().resolve()):
        return False, "Refusing to delete outside the model cache."
    with _lock:
        #: Let go of it first: a loaded model holds its files open on Windows.
        if _loaded is not None and _loaded[0] == size:
            _loaded = None
        try:
            import shutil

            shutil.rmtree(folder)
        except OSError:
            logger.warning("couldn't remove the Whisper %s model", safe_value(size, 40), exc_info=True)
            return False, f"Couldn't remove the {size} dictation model: see Settings, Logs for why."
    return True, f"The {size} dictation model is removed. It downloads again the next time you dictate with it."


def _get_model(size: str):  # noqa: ANN202  # faster_whisper types are optional
    global _loaded
    with _lock:
        if _loaded is None or _loaded[0] != size:
            from faster_whisper import WhisperModel  # imported only when present

            # int8 keeps memory modest on ordinary laptops.
            _loaded = (size, WhisperModel(size, device="cpu", compute_type="int8"))
        return _loaded[1]


def transcribe(audio_path: Path, model_size: str = "base", options: dict | None = None) -> str:
    """The clip's words as one line of text (see `transcribe_segments`)."""
    return " ".join(seg["text"] for seg in transcribe_segments(audio_path, model_size, options)).strip()


def transcribe_segments(audio_path: Path, model_size: str = "base", options: dict | None = None) -> list[dict]:
    """Every segment of one clip at once (see `iter_segments`)."""
    return list(iter_segments(audio_path, model_size, options))


def iter_segments(audio_path: Path, model_size: str = "base", options: dict | None = None) -> Iterator[dict]:
    """Turn one recorded clip into text, a segment at a time, so a background
    run can report how far it is and stop between two (UI_MODERNISATION V1). Raises RuntimeError with the
    install hint when Whisper isn't available, and RuntimeError with a
    distinct message when the model itself can't be loaded.

    That second case is not hypothetical: the first transcription on a
    machine downloads the model from Hugging Face, and a broken or
    offline connection makes that download raise deep inside
    faster-whisper/huggingface_hub: an exception that has nothing to do
    with the recording. Left uncaught, it surfaced as "Couldn't
    transcribe that recording: <httpx error>" (the route's catch-all for
    a bad clip), which reads exactly like "transcription is broken" and
    sends the user looking at their microphone instead of their network.
    """
    if not whisper_available():
        raise RuntimeError(INSTALL_HINT)
    try:
        model = _get_model(model_size)
    except Exception as exc:
        # The library's own error (a network failure deep in a download, a
        # corrupt cache) is for the log; the person gets the one thing they
        # can act on, which is nearly always the connection.
        logger.warning("Couldn't load the Whisper %s model", safe_value(model_size, 40), exc_info=True)
        raise RuntimeError(
            "Couldn't load the speech model. The first use downloads it, so "
            "check your internet connection and try again."
        ) from exc
    #: Settings' options unless the caller passed its own (`options_from`).
    kwargs = _options() if options is None else options
    try:
        segments, _info = model.transcribe(str(audio_path), **kwargs)
    except TypeError as exc:
        #: faster-whisper 1.1 opens the file with `av.open(..., metadata_errors=...)`,
        #: an argument PyAV 14 removed, so every clip failed on a fresh install
        #: (the owner's log, 2026-10-11). Decoding it here and handing over the
        #: samples skips that call on any pair of versions.
        if "metadata_errors" not in str(exc):
            raise
        segments, _info = model.transcribe(_decode_samples(audio_path), **kwargs)
    #: Each segment with its times (28.5 row 7): a transcript line seeks the
    #: player to its moment, and SRT and VTT are written from these.
    for segment in segments:
        if segment.text.strip():
            yield {"start": round(segment.start * 1000), "end": round(segment.end * 1000), "text": segment.text.strip()}


def _decode_samples(audio_path: Path, rate: int = 16000):  # noqa: ANN202
    """The clip as mono float32 samples at Whisper's 16 kHz, decoded with PyAV
    directly: the same steps as faster-whisper's own `decode_audio` (MIT),
    without the argument newer PyAV refuses."""
    import av
    import numpy as np

    resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
    chunks = []
    with av.open(str(audio_path), mode="r") as container:
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0
