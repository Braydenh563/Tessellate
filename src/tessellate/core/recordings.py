"""Where a recording's audio lives, and what may be written there.

A recording (`database.Recording`) is an object of its own (WORLD_CLASS_PLAN
"Audio in the notebook", decision 2), so its audio is not an attachment and
not a `/media` upload: it goes to `data_dir/recordings` under a random name,
appended one chunk at a time while the browser records. Only the containers
a browser's MediaRecorder makes are accepted (decision 3), and the claimed
type must agree with the file's first bytes, the same rule as the media
allowlist: a name or a header is never trusted on its own.
"""

from __future__ import annotations

import json
import secrets
import threading
from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from tessellate.core import deps, transcript
from tessellate.core.database import INCLUDE_BINNED, Recording, utcnow

#: A meeting or a lecture, several hours of opus; the voice route's ceiling.
MAX_RECORDING_BYTES = 300 * 1024 * 1024

#: The containers MediaRecorder writes (and the wav a trim writes), each with
#: the suffix it is stored under and a test of its first bytes.
CONTAINERS: dict[str, tuple[str, object]] = {
    "audio/webm": (".webm", lambda head: head[:4] == b"\x1a\x45\xdf\xa3"),
    "audio/ogg": (".ogg", lambda head: head[:4] == b"OggS"),
    "audio/mp4": (".m4a", lambda head: head[4:8] == b"ftyp"),
    "audio/wav": (".wav", lambda head: head[:4] == b"RIFF" and head[8:12] == b"WAVE"),
}

#: A recording with no chunk for this long is not being recorded any more:
#: the tab that made it was closed or killed (row 5).
STALE_AFTER = timedelta(seconds=45)

PEAKS_MAX = 2000
MARKERS_MAX = 500
MARK_NOTE_MAX = 500


def container(mime: str) -> str | None:
    """The accepted base type for a browser's `blob.type`, or None.
    "audio/webm;codecs=opus" is "audio/webm"; "video/webm" from an
    audio-only recorder is too (Chromium names it so on some builds)."""
    base = (mime or "").split(";", 1)[0].strip().lower()
    if base == "video/webm":
        base = "audio/webm"
    if base in ("audio/x-wav", "audio/wave"):
        base = "audio/wav"
    return base if base in CONTAINERS else None


def matches(mime: str, head: bytes) -> bool:
    check = CONTAINERS[mime][1]
    return bool(check(head))  # type: ignore[operator]


def directory() -> Path:
    path = deps.get_config().data_dir / "recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_filename(mime: str) -> str:
    return secrets.token_hex(16) + CONTAINERS[mime][0]


def path_of(recording: Recording) -> Path:
    return directory() / Path(recording.filename).name


def clean_peaks(values: object) -> str:
    out = [max(0, min(100, int(v))) for v in values if isinstance(v, (int, float))] if isinstance(values, list) else []
    return json.dumps(out[:PEAKS_MAX])


def clean_markers(values: object, duration_ms: int | None = None) -> str:
    """Marks as stored: a plain number of milliseconds, or `{at, note}` when
    the mark carries a comment (Brief 96). A number is what every recording
    saved before comments holds, so both read back the same way."""
    notes: dict[int, str] = {}
    for value in values if isinstance(values, list) else []:
        if isinstance(value, dict):
            at, note = value.get("at"), value.get("note")
        else:
            at, note = value, ""
        if not isinstance(at, (int, float)) or isinstance(at, bool):
            continue
        notes[max(0, int(at))] = str(note or "").strip()[:MARK_NOTE_MAX]
    times = sorted(t for t in notes if not duration_ms or t <= duration_ms)[:MARKERS_MAX]
    return json.dumps([{"at": t, "note": notes[t]} if notes[t] else t for t in times])


# --- transcription in the background (UI_MODERNISATION V1, INBOX 828) ----------
#
# A run per recording, in memory and for this process: closing the dialog or
# the Recordings tab never stops it, and the row reads its state and progress
# from here. The run itself is an `activity` job, so the running panel lists it
# with Stop, and the ledger keeps it after it ends.

_runs_lock = threading.Lock()
_runs: dict[int, dict] = {}
_done: dict[int, threading.Event] = {}


def transcription_of(recording_id: int) -> dict | None:
    with _runs_lock:
        run = _runs.get(recording_id)
        return dict(run) if run else None


def begin_transcription(recording_id: int, job_id: str) -> bool:
    """False when one is already running for this recording."""
    with _runs_lock:
        if (_runs.get(recording_id) or {}).get("state") == "running":
            return False
        _runs[recording_id] = {"state": "running", "progress": 0.0, "job_id": job_id, "error": "", "words": 0}
        _done[recording_id] = threading.Event()
        return True


def note_progress(recording_id: int, progress: float | None) -> None:
    with _runs_lock:
        if recording_id in _runs and progress is not None:
            _runs[recording_id]["progress"] = round(max(0.0, min(1.0, progress)), 3)


def end_transcription(recording_id: int, state: str, error: str = "", words: int = 0) -> None:
    with _runs_lock:
        run = _runs.setdefault(recording_id, {"job_id": ""})
        run.update(state=state, error=error, words=words, progress=1.0 if state == "done" else run.get("progress"))
        event = _done.pop(recording_id, None)
    if event is not None:
        event.set()


def wait_transcription(recording_id: int, timeout: float) -> bool:
    """For tests and shutdown: True once the run has ended (or none ran)."""
    with _runs_lock:
        event = _done.get(recording_id)
    return True if event is None else event.wait(timeout)


def _forget_runs() -> None:
    """A fresh data dir starts with no runs; its ids are reused."""
    with _runs_lock:
        _runs.clear()
        _done.clear()


deps.register_cache_reset(_forget_runs)


def as_dict(recording: Recording) -> dict:
    marks = transcript.marks_of(recording)
    return {
        "id": recording.id,
        "title": recording.title,
        "mime": recording.mime,
        "size_bytes": recording.size_bytes,
        "duration_ms": recording.duration_ms,
        "peaks": json.loads(recording.peaks or "[]"),
        "markers": [mark["at"] for mark in marks],
        #: The same moments with their comments (Brief 96).
        "marks": marks,
        #: The lines themselves are read on their own route: an hour is
        #: about 700 of them, and the shelf lists 500 recordings.
        "transcribed": (recording.segments or "[]") != "[]",
        "transcription": transcription_of(recording.id),
        "entry_id": recording.entry_id,
        "source_id": recording.source_id,
        "derived": recording.derived or "",
        "state": recording.state,
        "recovered": recording.recovered,
        "created_at": recording.created_at.isoformat() if recording.created_at else None,
    }


def recover_stale(session: Session) -> list[Recording]:
    """Finish every recording whose tab stopped sending chunks: what was
    saved is kept, marked recovered so the app says so once. Commits."""
    cutoff = utcnow() - STALE_AFTER
    rows = (
        session.query(Recording)
        .filter(Recording.state == "recording", Recording.updated_at < cutoff)
        .all()
    )
    for row in rows:
        if row.size_bytes:
            row.state = "saved"
            row.recovered = True
        else:
            # Nothing was ever written: there is nothing to recover.
            path_of(row).unlink(missing_ok=True)
            session.delete(row)
    if rows:
        session.commit()
    return [row for row in rows if row.recovered]


def _binned(session: Session) -> list[Recording]:
    old = session.info.get(INCLUDE_BINNED)
    session.info[INCLUDE_BINNED] = True
    try:
        return (
            session.query(Recording)
            .filter(Recording.deleted_at.is_not(None))
            .order_by(Recording.deleted_at.desc())
            .all()
        )
    finally:
        if old is None:
            session.info.pop(INCLUDE_BINNED, None)
        else:
            session.info[INCLUDE_BINNED] = old


def binned(session: Session) -> list[Recording]:
    """The recordings in the bin, newest first."""
    return _binned(session)


def purge(session: Session, recording: Recording) -> None:
    """Delete a recording and its audio for good. Does not commit."""
    path_of(recording).unlink(missing_ok=True)
    session.delete(recording)


def empty(session: Session) -> int:
    """Delete every binned recording. Does not commit."""
    rows = _binned(session)
    for row in rows:
        purge(session, row)
    return len(rows)


def purge_expired(session: Session, days: int) -> int:
    """Drop recordings binned more than `days` ago. Does not commit."""
    cutoff = utcnow() - timedelta(days=days)
    rows = [row for row in _binned(session) if row.deleted_at < cutoff]
    for row in rows:
        purge(session, row)
    return len(rows)
