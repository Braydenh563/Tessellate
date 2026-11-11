"""Speaker labels by voice, all on this computer (BACKLOG 102 item 8, gap 12).

`ai/speakers.py` names turns from what is said and needs a model. This tells
voices apart from the audio and needs neither: sherpa-onnx (onnxruntime, no
torch) runs a pyannote segmentation model and a speaker-embedding model, both
pinned downloads in the data dir (`core/extras.py`, the "speakers" and
"speakermodels" extras, one bundle). Transcripts then read "Speaker 1",
"Speaker 2" in the order the voices first speak; the person renames a label
once (`PUT /recordings/{id}/speakers`) and the stored transcript keeps the name.

**With the extra absent nothing changes**: `available()` is False, the
transcription routes never call in here, and the lines keep whatever
`speakers.label` gave them.

**One voice labels nothing.** A talk by one person has nobody to tell apart,
and "Speaker 1" on every line is noise; a label is never a guess dressed as a
fact (the rule `speakers.py` keeps too).

**The seam.** `set_runner` replaces the engine call with a function from an
audio path to spans, so tests never load a model (CLAUDE.md section 4: real
inference is unverified in tests; the real engine was run once by hand on a
public four-speaker clip, and the numbers are in the CHANGELOG line).
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Callable
from pathlib import Path

from tessellate.ai import voice
from tessellate.core import extras, transcript

logger = logging.getLogger(__name__)

#: Named by the feature, as the voice add-on's hint is: what to install, where.
INSTALL_HINT = (
    "Telling voices apart needs “Speaker labels” in Settings, Packages. "
    "Install the Speakers bundle, then try again."
)

#: The two model files the "speakermodels" extra writes (names fixed there).
SEGMENTATION = "segmentation.onnx"
EMBEDDING = "embedding.onnx"
#: Extra ids: the engine (pip) and its models (pinned downloads).
ENGINE_EXTRA = "speakers"
MODELS_EXTRA = "speakermodels"

#: `(start ms, end ms, voice number)`; the number is the engine's, meaningless
#: beyond "the same voice".
Span = tuple[int, int, int]

#: Cosine-distance threshold of the clustering; sherpa-onnx's own example value.
CLUSTER_THRESHOLD = 0.5
#: Speech shorter than this, or a gap shorter than this, is not a turn.
MIN_ON_S = 0.3
MIN_OFF_S = 0.5
THREADS = 2

_runner: Callable[[Path], list[Span]] | None = None


def set_runner(runner: Callable[[Path], list[Span]] | None) -> None:
    """The test seam: `runner(audio_path)` stands in for the engine; None
    puts the real one back."""
    global _runner
    _runner = runner


def engine_installed() -> bool:
    try:
        return importlib.util.find_spec("sherpa_onnx") is not None
    except (ImportError, ValueError):
        return False


def model_folder() -> Path | None:
    """The data-dir folder holding both model files, or None until installed."""
    return extras.download_ready(MODELS_EXTRA)


def available() -> bool:
    return _runner is not None or (engine_installed() and model_folder() is not None)


def spans(audio_path: Path) -> list[Span]:
    """Who speaks when, from the audio: the runner if one is set, else
    sherpa-onnx over the clip decoded to 16 kHz mono. Raises if the engine
    or a model will not load; the caller keeps the lines unlabelled."""
    if _runner is not None:
        return _runner(audio_path)
    folder = model_folder()
    if folder is None or not engine_installed():
        raise RuntimeError("Telling voices apart needs “Speaker labels” in Settings, Packages.")
    import sherpa_onnx

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(folder / SEGMENTATION)),
            num_threads=THREADS,
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(folder / EMBEDDING), num_threads=THREADS),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=CLUSTER_THRESHOLD),
        min_duration_on=MIN_ON_S,
        min_duration_off=MIN_OFF_S,
    )
    engine = sherpa_onnx.OfflineSpeakerDiarization(config)
    samples = voice._decode_samples(audio_path, rate=engine.sample_rate)
    found = engine.process(samples).sort_by_start_time()
    return [(round(one.start * 1000), round(one.end * 1000), int(one.speaker)) for one in found]


def _overlap(seg: dict, span: Span) -> int:
    return max(0, min(seg["end"], span[1]) - max(seg["start"], span[0]))


def _gap(seg: dict, span: Span) -> int:
    return max(span[0] - seg["end"], seg["start"] - span[1], 0)


def assign(segments: list[dict], found: list[Span]) -> list[dict]:
    """The segments with `speaker` set to "Speaker N" from the spans: each
    line takes the voice that covers most of it, or, in a gap, the nearest
    voice within a turn-length pause (`transcript.TURN_PAUSE_MS`), else none.
    N counts voices in the order they first speak. Fewer than two voices
    labels nothing. The input is not changed."""
    if len({span[2] for span in found}) < 2:
        return [dict(seg) for seg in segments]
    picked: list[int | None] = []
    for seg in segments:
        best = max(found, key=lambda span: (_overlap(seg, span), -_gap(seg, span)), default=None)
        if best is not None and _overlap(seg, best) == 0 and _gap(seg, best) > transcript.TURN_PAUSE_MS:
            best = None
        picked.append(best[2] if best is not None else None)
    numbers: dict[int, int] = {}
    out = []
    for seg, voice_id in zip(segments, picked, strict=True):
        label = None
        if voice_id is not None:
            label = f"Speaker {numbers.setdefault(voice_id, len(numbers) + 1)}"
        out.append({**seg, "speaker": label})
    return out


def speaker_count(segments: list[dict]) -> int:
    return len({seg["speaker"] for seg in segments if seg.get("speaker")})


def label_audio(segments: list[dict], audio_path: Path) -> list[dict]:
    """`segments` labelled from the audio, or as they were when the engine
    fails: a transcript is never lost to a label."""
    try:
        return transcript.clean(assign(segments, spans(audio_path)))
    except Exception:  # noqa: BLE001  # any engine or decode failure leaves the lines as they were
        logger.warning("telling the voices apart failed", exc_info=True)
        return segments
