"""Where speech is in a clip, by Silero VAD, all on this computer (Brief 87, L691).

**Optional, never vendored.** The engine is `onnxruntime` (a pip extra, `vad`) and
the model is one pinned 2.3 MB file (`vad-model`, MIT, snakers4/silero-vad), both
fetched on an Install click in Settings, Packages, as the natural voice is. This
reads the model directly: no torch, no `silero-vad` wheel.

**With the extra absent nothing changes**: `available()` is False and a caller keeps
what it did before (`voice.options_from` already hands faster-whisper its own
bundled copy of this model for `vad_filter`; this module is for the callers that
want the segments themselves, such as trimming a recording or captions deciding a
chunk is silence).

**The model.** v5 reads 512 samples at 16 kHz (32 ms) per call, with the last 64
samples of the previous window in front of it and a `(2, 1, 128)` recurrent state
carried between calls. It answers one probability. A window is speech above
`THRESHOLD` and stays speech until the probability falls under `THRESHOLD - 0.15`
(the model's own hysteresis), so one quiet frame does not split a word.

**The seam.** `set_runner` replaces the engine with a function from samples to
per-window probabilities, so tests never load a model (CLAUDE.md section 4: real
inference is unverified in tests; the real model was run once on a synthetic
signal and the numbers are in the CHANGELOG line).
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from tessellate.core import extras

logger = logging.getLogger(__name__)

INSTALL_HINT = (
    "Finding speech needs “Speech detection” in Settings, Packages. "
    "Install the Speech detection bundle, then try again."
)

ENGINE_EXTRA = "vad"
MODEL_EXTRA = "vad-model"
MODEL_FILE = "silero_vad.onnx"

RATE = 16_000
WINDOW = 512
CONTEXT = 64
#: A window is speech at or above this; it stays speech until it falls under `THRESHOLD - HYSTERESIS`.
THRESHOLD = 0.5
HYSTERESIS = 0.15
#: A run shorter than this is a click, not speech; a gap shorter than this is a breath inside a phrase.
MIN_SPEECH_MS = 250
MIN_SILENCE_MS = 100
#: Each segment is widened by this much so a word's edge is not clipped.
PAD_MS = 30

#: `(start ms, end ms)` of one stretch of speech.
Segment = tuple[int, int]

_runner: Callable[[Sequence[float]], list[float]] | None = None


def set_runner(runner: Callable[[Sequence[float]], list[float]] | None) -> None:
    """The test seam: `runner(samples)` returns one probability per `WINDOW`; None puts the real one back."""
    global _runner
    _runner = runner


def engine_installed() -> bool:
    try:
        return importlib.util.find_spec("onnxruntime") is not None
    except (ImportError, ValueError):
        return False


def model_path() -> Path | None:
    folder = extras.download_ready(MODEL_EXTRA)
    return folder / MODEL_FILE if folder else None


def available() -> bool:
    return _runner is not None or (engine_installed() and model_path() is not None)


def probabilities(samples) -> list[float]:  # noqa: ANN001  # a float32 array at 16 kHz, mono
    """The model's speech probability for each `WINDOW` of the samples (the tail is zero-padded)."""
    if _runner is not None:
        return _runner(samples)
    path = model_path()
    if path is None or not engine_installed():
        raise RuntimeError(INSTALL_HINT)
    import numpy as np
    import onnxruntime

    options = onnxruntime.SessionOptions()
    options.inter_op_num_threads = 1
    options.intra_op_num_threads = 1
    session = onnxruntime.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    tail = (-len(audio)) % WINDOW
    if tail:
        audio = np.concatenate([audio, np.zeros(tail, dtype=np.float32)])
    state = np.zeros((2, 1, 128), dtype=np.float32)
    context = np.zeros(CONTEXT, dtype=np.float32)
    rate = np.array(RATE, dtype=np.int64)
    found: list[float] = []
    for start in range(0, len(audio), WINDOW):
        window = audio[start : start + WINDOW]
        heard = np.concatenate([context, window])[None, :]
        out, state = session.run(None, {"input": heard, "state": state, "sr": rate})
        found.append(float(out[0][0]))
        context = heard[0, -CONTEXT:]
    return found


def segments_from(probs: Sequence[float], total_ms: int | None = None) -> list[Segment]:
    """Speech stretches from per-window probabilities: the hysteresis, the minimum run and gap, the padding."""
    step = WINDOW * 1000 / RATE
    runs: list[list[float]] = []
    inside = False
    for index, probability in enumerate(probs):
        if probability >= THRESHOLD or (inside and probability >= THRESHOLD - HYSTERESIS):
            if not inside:
                runs.append([index * step, (index + 1) * step])
                inside = True
            else:
                runs[-1][1] = (index + 1) * step
        else:
            inside = False
    merged: list[list[float]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] < MIN_SILENCE_MS:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    end = total_ms if total_ms is not None else len(probs) * step
    return [
        (max(0, round(start - PAD_MS)), min(round(end), round(stop + PAD_MS)))
        for start, stop in merged
        if stop - start >= MIN_SPEECH_MS
    ]


def speech_segments(samples) -> list[Segment]:  # noqa: ANN001
    """Where speech is in 16 kHz mono float samples, as `(start ms, end ms)`."""
    return segments_from(probabilities(samples), round(len(samples) * 1000 / RATE))


def speech_in(audio_path: Path) -> list[Segment]:
    """Where speech is in an audio file (decoded to 16 kHz mono, as Whisper reads it)."""
    from tessellate.ai import voice

    return speech_segments(voice._decode_samples(audio_path, rate=RATE))


def speech_share(segments: Sequence[Segment], total_ms: int) -> float:
    """The fraction of the clip that is speech, 0 to 1."""
    return min(1.0, sum(stop - start for start, stop in segments) / total_ms) if total_ms > 0 else 0.0
