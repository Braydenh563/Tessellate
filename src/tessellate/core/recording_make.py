"""A recording the app made, not the person (the studio's overview, WORLD_CLASS row 35).

Kept exactly as a take from the microphone is: a row in `recordings` with its file under
`data_dir/recordings`, a waveform, and the timed transcript lines, so it plays, seeks and
is found by search like any other (`derived` says it was made here, from what).
"""

from __future__ import annotations

import array
import io
import wave

from tessellate.core import deps, recordings, transcript
from tessellate.core.database import Recording
from tessellate.entry.manager import log_action

#: Bars in the saved waveform: the recorder draws about as many.
PEAK_BARS = 120


def peaks_of(wav: bytes, bars: int = PEAK_BARS) -> list[int]:
    """0 to 100 levels, one per slice of the wav (the loudest sample in it)."""
    with wave.open(io.BytesIO(wav)) as audio:
        samples = array.array("h")
        samples.frombytes(audio.readframes(audio.getnframes()))
    if not samples:
        return []
    step = max(1, len(samples) // bars)
    loudest = max(1, max(abs(s) for s in samples))
    return [min(100, round(100 * max(abs(s) for s in samples[i : i + step]) / loudest)) for i in range(0, len(samples), step)][
        :bars
    ]


def duration_ms(wav: bytes) -> int:
    with wave.open(io.BytesIO(wav)) as audio:
        return audio.getnframes() * 1000 // audio.getframerate()


def save_generated(
    title: str, wav: bytes, segments: list[dict], *, derived: str, workspace: str | None = None
) -> int:
    """Store a wav and its lines as a finished recording; its id. Opens its own session,
    so a background thread can call it (the request's session is long closed)."""
    mime = "audio/wav"
    row = Recording(
        title=title.strip()[:200],
        mime=mime,
        filename=recordings.new_filename(mime),
        size_bytes=len(wav),
        duration_ms=duration_ms(wav),
        peaks=recordings.clean_peaks(peaks_of(wav)),
        segments=transcript.dumps(segments),
        derived=derived,
        state="saved",
    )
    session = deps.get_db().session()
    if workspace:
        session.info["workspace_id"] = workspace
    try:
        recordings.path_of(row).write_bytes(wav)
        session.add(row)
        session.flush()
        log_action(session, "created", "recording", row.id, detail=derived)
        session.commit()
        return row.id
    finally:
        session.close()
