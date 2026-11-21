"""Recordings (WORLD_CLASS_PLAN 28.5 rows 1, 5 and 6): audio kept as an
object of its own (decision 2), named by the container the browser made
(decision 3), and transcribed only when the optional add-on is there
(decision 4).

**Record never refuses.** With no Whisper add-on the audio is still kept:
the recorder makes a row here before the first chunk, appends a chunk every
10 seconds, and finishes it on Stop. A tab killed mid-meeting leaves every
chunk it sent; `recordings.recover_stale` finishes such a row the next time
the list is read, marked recovered so the app says so once.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from tessellate.ai import diarize, speakers, voice
from tessellate.api import paging
from tessellate.api.downloads import attachment_headers, sealed_aware, sealed_http
from tessellate.core import activity, deps, jobs, recording_trim, recordings, sealed_files, spacelock, transcript, vault
from tessellate.core.database import LIKE_ESCAPE, Entry, Recording, SealedWriteRefused, like_escape, utcnow
from tessellate.core.deps import get_session
from tessellate.entry import bin as other_bin
from tessellate.entry import manager_text
from tessellate.entry import meetings as meeting_shape
from tessellate.entry.manager import log_action
from tessellate.repo import content as content_repo

router = APIRouter(tags=["recordings"])
#: `<audio src>` sends the media cookie, never the X-Auth-Token header, so
#: the audio is served under `/media/`, the cookie's own path, on the media
#: gate (`routes_auth.MEDIA_COOKIE_PATHS`).
media_router = APIRouter(tags=["recordings"])

logger = logging.getLogger("tessellate.recordings")


class RecordingCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    mime: str = Field(default="audio/webm", max_length=120)
    entry_id: int | None = None
    #: A trim's original (row 6): the new object says where it came from.
    source_id: int | None = None
    #: "trim" or "enhanced" (V3) when made from `source_id`.
    derived: Literal["", "trim", "enhanced"] = ""


class RecordingFinish(BaseModel):
    duration_ms: int = Field(default=0, ge=0, le=24 * 3600 * 1000)
    peaks: list[float] = Field(default_factory=list, max_length=recordings.PEAKS_MAX)
    markers: list[float | dict] = Field(default_factory=list, max_length=recordings.MARKERS_MAX)


class RecordingTrim(BaseModel):
    start_ms: int = Field(ge=0, le=24 * 3600 * 1000)
    end_ms: int = Field(gt=0, le=24 * 3600 * 1000)

    @model_validator(mode="after")
    def _ordered(self) -> RecordingTrim:
        if self.end_ms <= self.start_ms:
            raise ValueError("The end must come after the start.")
        return self


class RecordingPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    #: A number, or `{at, note}` for a mark with a comment (Brief 96).
    markers: list[float | dict] | None = Field(default=None, max_length=recordings.MARKERS_MAX)
    entry_id: int | None = None


def _get(session: Session, recording_id: int, binned: bool = False) -> Recording:
    if binned:
        with other_bin.including_binned(session):
            row = session.get(Recording, recording_id)
    else:
        row = session.get(Recording, recording_id)
        if row is not None and row.deleted_at is not None:
            row = None
    if row is None:
        raise HTTPException(status_code=404, detail="That recording could not be found.")
    return row


def _writable(session: Session, recording_id: int) -> Recording:
    """A write's row: 404 for none, 409 for one in the bin (`repo/content`)."""
    return content_repo.RECORDINGS.writable(session, recording_id)


#: A page of the library; the screen asks for the largest and filters it itself.
RECORDINGS_PAGE_SIZE = 100
RECORDINGS_PAGE_SIZE_MAX = 500


@router.get("/recordings")
def list_recordings(
    response: Response,
    limit: int = Query(default=RECORDINGS_PAGE_SIZE, ge=1, le=RECORDINGS_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    q: str = Query(default="", max_length=200),
    session: Session = Depends(get_session),
) -> dict:
    """Newest first, a page at a time (`X-Total-Count` is the whole library),
    after finishing any take a closed tab left unfinished (row 5): `recovered` lists
    those, once. `q` keeps the recordings whose name or transcript has the
    words, each with `match`: the first transcript line that has them and
    when it was said (the library's own search box, which used to read names
    alone)."""
    offset = paging.start(cursor, offset)
    recovered = recordings.recover_stale(session)
    query = session.query(Recording).filter(Recording.state == "saved")
    needle = " ".join(q.split())
    if needle:
        # The transcript is stored as JSON, so a quote in the words is `\"` there.
        stored = json.dumps(needle, ensure_ascii=False)[1:-1]
        query = query.filter(
            or_(
                Recording.title.ilike(f"%{like_escape(needle)}%", escape=LIKE_ESCAPE),
                Recording.segments.ilike(f"%{like_escape(stored)}%", escape=LIKE_ESCAPE),
            )
        )
    total = query.count()
    rows = query.order_by(Recording.created_at.desc()).offset(offset).limit(limit).all()
    response.headers["X-Total-Count"] = str(total)
    paging.finish(response, offset, limit, total)
    announced = [recordings.as_dict(row) for row in recovered]
    found = [recordings.as_dict(row) for row in rows]
    if needle:
        for row, item in zip(rows, found, strict=True):
            item["match"] = transcript.first_match(row.segments, needle)
    return {"recordings": found, "recovered": announced}


@router.post("/recordings/recover")
def recover_recordings(session: Session = Depends(get_session)) -> list[dict]:
    """Run at each start: the recordings a closed tab left half-made, each
    finished with every chunk it sent (row 5), listed once. A bare list: the
    call is in app.js, whose boot bytes are ratcheted."""
    return [recordings.as_dict(row) for row in recordings.recover_stale(session)]


@router.post("/recordings", status_code=201)
def create_recording(body: RecordingCreate, session: Session = Depends(get_session)) -> dict:
    mime = recordings.container(body.mime)
    if mime is None:
        raise HTTPException(
            status_code=415,
            detail="This browser records in a format the app can't keep (webm, ogg, mp4 or wav).",
        )
    row = Recording(
        title=body.title.strip()[:200],
        mime=mime,
        filename=recordings.new_filename(mime),
        entry_id=body.entry_id,
        source_id=body.source_id,
        derived=body.derived,
        state="recording",
    )
    session.add(row)
    session.flush()
    log_action(session, "created", "recording", row.id, detail=mime)
    session.commit()
    return recordings.as_dict(row)


def _append(session: Session, row: Recording, data: bytes) -> None:
    """Append, or leave the file as it was: a write cut short (a full disk)
    is cut back, so the retry starts where the saved audio ends. The error
    goes on to the app's handler, which answers a full disk with 507. A
    private space's recording is sealed from its first chunk (L-world-class-52)."""
    try:
        sealed_files.append(recordings.path_of(row), data, sealed=sealed_files.wanted(session, row.workspace_id))
    except sealed_files.LooksSealed as exc:
        raise HTTPException(status_code=415, detail=sealed_files.LOOKS_SEALED_DETAIL) from exc


@router.post("/recordings/{recording_id}/chunk")
def append_chunk(
    recording_id: int,
    file: UploadFile,
    duration_ms: int = Form(0),
    at: int = Form(-1),
    session: Session = Depends(get_session),
) -> dict:
    """One slice of a recording in progress, appended to its file. The first
    must open with the container's own header (the type check). `at` is the
    size the sender thinks the file has: a retried slice that already landed
    is answered, not written twice, and one out of step is refused (audit
    1030 Y1)."""
    row = _writable(session, recording_id)
    if row.state != "recording":
        raise HTTPException(status_code=409, detail="That recording is already finished.")
    room = recordings.MAX_RECORDING_BYTES - row.size_bytes
    data = file.file.read(room + 1)
    if at >= 0 and at != row.size_bytes:
        if at + len(data) == row.size_bytes:
            return {"id": row.id, "size_bytes": row.size_bytes, "duration_ms": row.duration_ms}
        raise HTTPException(status_code=409, detail="That slice is out of step with the saved recording.")
    if len(data) > room:
        raise HTTPException(status_code=413, detail="That recording is larger than 300 MB.")
    if not row.size_bytes and data and not recordings.matches(row.mime, data[:16]):
        raise HTTPException(status_code=415, detail="That audio isn't the type it says it is.")
    if data:
        _append(session, row, data)
        row.size_bytes += len(data)
    row.duration_ms = max(row.duration_ms, min(int(duration_ms), 24 * 3600 * 1000))
    row.updated_at = utcnow()
    session.commit()
    return {"id": row.id, "size_bytes": row.size_bytes, "duration_ms": row.duration_ms}


@router.post("/recordings/{recording_id}/finish")
def finish_recording(
    recording_id: int, body: RecordingFinish, session: Session = Depends(get_session)
) -> dict:
    row = _writable(session, recording_id)
    if not row.size_bytes:
        recordings.purge(session, row)
        session.commit()
        raise HTTPException(status_code=400, detail="The recording is empty.")
    row.state = "saved"
    row.duration_ms = max(row.duration_ms, body.duration_ms)
    row.peaks = recordings.clean_peaks(body.peaks)
    row.markers = recordings.clean_markers(body.markers, row.duration_ms or None)
    row.updated_at = utcnow()
    session.commit()
    return recordings.as_dict(row)


@router.post("/recordings/{recording_id}/trim", status_code=201)
def trim_recording(recording_id: int, body: RecordingTrim, session: Session = Depends(get_session)) -> dict:
    """The part from `start_ms` to `end_ms` as a new wav recording that points
    at its original (L632). The cut is made here, packet by packet, so the page
    never decodes the whole take; the original is kept, and its waveform and
    marks are carried over for the span."""
    row = _writable(session, recording_id)
    path = recordings.path_of(row)
    if row.state != "saved" or not path.is_file():
        raise HTTPException(status_code=404, detail="That recording's audio is missing.")
    end = min(body.end_ms, row.duration_ms) if row.duration_ms else body.end_ms
    if end <= body.start_ms:
        raise HTTPException(status_code=422, detail="The end must come after the start.")
    try:
        with sealed_files.readable(path) as audio:
            wav = recording_trim.cut(Path(audio), body.start_ms, end)
    except sealed_files.SealedError as exc:
        raise sealed_http(exc) from exc
    except recording_trim.TrimError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    span = row.duration_ms or end
    bars = json.loads(row.peaks or "[]")
    kept_marks = [
        ({"at": m["at"] - body.start_ms, "note": m["note"]} if m.get("note") else m["at"] - body.start_ms)
        for m in transcript.marks_of(row)
        if body.start_ms <= m["at"] <= end
    ]
    made = Recording(
        title=f"{row.title or 'Recording'} (trimmed)"[:200],
        mime="audio/wav",
        filename=recordings.new_filename("audio/wav"),
        entry_id=row.entry_id,
        source_id=row.id,
        derived="trim",
        state="saved",
        size_bytes=len(wav),
        duration_ms=end - body.start_ms,
        peaks=recordings.clean_peaks(bars[int(body.start_ms / span * len(bars)) : -(-end * len(bars) // span)]),
    )
    made.markers = recordings.clean_markers(kept_marks, made.duration_ms)
    try:
        sealed_files.append(recordings.path_of(made), wav, sealed=sealed_files.wanted(session, row.workspace_id))
    except sealed_files.LooksSealed as exc:
        raise HTTPException(status_code=415, detail=sealed_files.LOOKS_SEALED_DETAIL) from exc
    session.add(made)
    session.flush()
    log_action(session, "created", "recording", made.id, detail="trim")
    session.commit()
    return recordings.as_dict(made)


@router.get("/recordings/{recording_id}")
def read_recording(recording_id: int, session: Session = Depends(get_session)) -> dict:
    return recordings.as_dict(_get(session, recording_id))


@router.patch("/recordings/{recording_id}")
def update_recording(
    recording_id: int, body: RecordingPatch, session: Session = Depends(get_session)
) -> dict:
    row = _writable(session, recording_id)
    if body.title is not None:
        row.title = body.title.strip()[:200]
    if body.markers is not None:
        row.markers = recordings.clean_markers(body.markers, row.duration_ms or None)
    if "entry_id" in body.model_fields_set:
        row.entry_id = body.entry_id
    session.commit()
    return recordings.as_dict(row)


@router.delete("/recordings/{recording_id}")
def bin_recording(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """Into the bin, audio and all; Restore brings it back as it was."""
    row = _writable(session, recording_id)
    row.deleted_at = utcnow()
    log_action(session, "binned", "recording", row.id)
    session.commit()
    return {"id": row.id, "binned": True}


@router.post("/recordings/{recording_id}/restore")
def restore_recording(recording_id: int, session: Session = Depends(get_session)) -> dict:
    row, _was_binned = content_repo.restore(session, "recording", recording_id)
    session.commit()
    return recordings.as_dict(row)


@router.delete("/recordings/{recording_id}/purge")
def purge_recording(recording_id: int, session: Session = Depends(get_session)) -> dict:
    with other_bin.including_binned(session):
        row = _get(session, recording_id, binned=True)
        if row.deleted_at is None:
            raise HTTPException(status_code=409, detail="Only a recording in the bin can be deleted for good.")
        recordings.purge(session, row)
        session.commit()
    return {"id": recording_id, "purged": True}


@router.post("/recordings/{recording_id}/transcribe")
def transcribe_recording(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """The kept audio, transcribed by the optional add-on (decision 4), its
    segments kept with their times on the recording (28.5 row 7). With no
    add-on: 503 and the hint, and the recording is unaffected."""
    row = _writable(session, recording_id)
    if not voice.whisper_available():
        raise HTTPException(status_code=503, detail=voice.INSTALL_HINT)
    path = recordings.path_of(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That recording's audio is missing.")
    try:
        with activity.track("transcription", "Transcribing a recording", stoppable=False), sealed_files.readable(path) as audio:
            segments = voice.transcribe_segments(
                Path(audio), model_size=deps.get_config().get_preference("voice_model", "base")
            )
            kept = transcript.clean(segments)
            if diarize.available():
                kept = diarize.label_audio(kept, Path(audio))
    except sealed_files.SealedError as exc:
        raise sealed_http(exc) from exc
    except RuntimeError as exc:
        logger.warning("transcription failed: %s", exc)
        raise HTTPException(status_code=503, detail=_sentence(exc, TRANSCRIBE_FAILED)) from exc
    except Exception as exc:  # a bad clip must not 500 mysteriously
        logger.warning("transcription failed", exc_info=True)
        raise HTTPException(
            status_code=422, detail="Couldn't transcribe that recording. Try recording it again."
        ) from exc
    kept = _named_if_unlabelled(session, row, kept)
    row.segments = transcript.dumps(kept)
    log_action(session, "transcribed", "recording", row.id)
    session.commit()
    return {"text": " ".join(seg["text"] for seg in kept), "segments": kept}


#: A space turned ordinary that kept its files private still holds sealed
#: audio, and a run outside a private space has no session to act for.
SEALED_OUTSIDE_PRIVATE = "This recording is kept private, so it can't be transcribed in the background."


def _acting_for(session: Session, row: Recording, path: Path) -> str | None:
    """The session a background run on `row` acts for (L-world-class-381):
    the caller's, for a private space's recording, so the run opens the
    sealed audio and writes the sealed transcript as that session and stops
    when its private-space door shuts (`sealed_files.for_background`). None
    for an ordinary space's recording, which needs no key; 409 up front for
    a sealed one there, as before the change."""
    if not sealed_files.wanted(session, row.workspace_id):
        if sealed_files.is_sealed(path):
            raise HTTPException(status_code=409, detail=SEALED_OUTSIDE_PRIVATE)
        return None
    token = vault.requester()
    if token is None or not spacelock.opened(token):
        raise HTTPException(status_code=423, detail=sealed_files.LOCKED_DETAIL)
    return token


@router.post("/recordings/{recording_id}/transcribe/start", status_code=202)
def start_transcription(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """The same transcription as a background run (UI_MODERNISATION V1): it
    returns at once, closing the dialog or the tab never stops it, the row
    and the running panel show how far it is, and Stop ends it between two
    segments, keeping nothing. 409 while one is already running."""
    row = _writable(session, recording_id)
    if not voice.whisper_available():
        raise HTTPException(status_code=503, detail=voice.INSTALL_HINT)
    path = recordings.path_of(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That recording's audio is missing.")
    token = _acting_for(session, row, path)
    name = row.title or "a recording"
    job = activity.start("transcription", f"Transcribing “{name}”", stoppable=True)
    if not recordings.begin_transcription(row.id, job.id):
        activity.finish(job)
        raise HTTPException(status_code=409, detail="That recording is already being transcribed.")
    work = (row.id, Path(path), row.duration_ms, deps.get_config().get_preference("voice_model", "base"),
            session.info.get("workspace_id"), job, token)
    #: A thread Job (`jobs.thread`, decision 58); the Stop route ends it between
    #: two segments, so the registry entry has no stopper of its own.
    jobs.thread(f"transcribe-{row.id}", lambda: _transcribe_in_background(*work))
    return {"id": row.id, "job_id": job.id, "transcription": recordings.transcription_of(row.id)}


@router.post("/recordings/{recording_id}/transcribe/stop")
def stop_transcription(recording_id: int, session: Session = Depends(get_session)) -> dict:
    _writable(session, recording_id)
    run = recordings.transcription_of(recording_id)
    if not run or run.get("state") != "running":
        return {"stopped": False, "detail": "Nothing is transcribing that recording."}
    stopped, detail = activity.stop(run["job_id"])
    return {"stopped": stopped, "detail": detail}


def _transcribe_in_background(
    recording_id: int, path: Path, duration_ms: int, model_size: str, workspace: str | None, job: activity.Job,
    token: str | None = None,
) -> None:
    kept: list[dict] = []
    state, error = "done", ""
    try:
        with sealed_files.for_background(path, token) as (audio, check):
            for segment in voice.iter_segments(audio, model_size=model_size):
                check()
                if job.stopped:
                    state = "stopped"
                    break
                kept.append(segment)
                if duration_ms:
                    job.update(done=min(segment["end"], duration_ms), total=duration_ms)
                    recordings.note_progress(recording_id, job.progress)
                job.update(detail=f"{len(kept)} lines heard")
            if state == "done":
                kept = _voice_labelled(kept, audio, job)
                if job.stopped:
                    state = "stopped"
                else:
                    check()
                    _keep_segments(recording_id, kept, workspace, check, named=token is None)
    except RuntimeError as exc:
        logger.warning("background transcription failed: %s", exc)
        state, error = "failed", _sentence(exc, TRANSCRIBE_FAILED)
    except Exception:  # noqa: BLE001  # a bad clip is a row that says so, never a dead thread
        logger.warning("background transcription failed", exc_info=True)
        state, error = "failed", TRANSCRIBE_FAILED
    finally:
        words = sum(len(seg["text"].split()) for seg in kept) if state == "done" else 0
        _record_failure(job, state, error)
        job.result = {"done": f"{words} words", "stopped": "stopped", "failed": error}[state]
        activity.finish(job)
        recordings.end_transcription(recording_id, state, error, words)


class RunFailed(RuntimeError):
    """A background run's own failure, worded for the person."""


TRANSCRIBE_FAILED = "Couldn't transcribe that recording. Try recording it again."
VOICES_FAILED = "Couldn't tell the voices apart. See Settings, Logs for why."


def _sentence(exc: RuntimeError, fallback: str) -> str:
    """A background run's failure line. Only a sentence written for the
    person is shown: this module's `RunFailed`, the speech module's
    `SpeechError`, a sealed-file error. A sealed write refused because the
    vault locked mid-run is the locked line, never the database's words
    (SECURITY.md T28). Any other RuntimeError (a model's, a library's) is the
    fixed `fallback`; its text is in the log where it is caught."""
    if isinstance(exc, SealedWriteRefused):
        return sealed_files.BACKGROUND_LOCKED_DETAIL
    if isinstance(exc, (RunFailed, voice.SpeechError, sealed_files.SealedError)):
        return str(exc)
    return fallback


def _record_failure(job: activity.Job, state: str, error: str) -> None:
    """The run's last-run line for a background job that ended "failed".
    `error` comes from `_sentence` or is one of the two fixed lines above, so
    it is never an arbitrary exception's text (that is logged where it is
    caught)."""
    if job.run is not None and state == "failed":
        job.run.fail(error)


def _voice_labelled(kept: list[dict], path: Path, job: activity.Job) -> list[dict]:
    """The lines with speakers from the audio when the Speakers bundle is
    installed. Done before the row is opened: it takes minutes on a long
    meeting and holds no database session."""
    if job.stopped or not diarize.available():
        return kept
    job.update(detail="Telling the voices apart")
    return diarize.label_audio(transcript.clean(kept), path)


def _open_door() -> None:
    """An ordinary space's run: no door to look at."""


def _keep_segments(
    recording_id: int, segments: list[dict], workspace: str | None, check: Callable[[], None] = _open_door, *,
    named: bool = True,
) -> None:
    """Write the transcript. A private space's run (`named` False) is never
    read by the model in the background, nor is its meeting note (SECURITY.md
    T28, T10), and `check` is asked immediately before the commit, so a lock
    at any step before it keeps nothing (review of L-world-class-381)."""
    session = deps.get_db().session()
    if workspace:
        session.info["workspace_id"] = workspace
    try:
        row = session.query(Recording).filter(Recording.id == recording_id).first()
        if row is None:
            raise RunFailed("That recording was deleted while it was transcribed.")
        kept = transcript.clean(segments)
        if named:
            kept = _named_if_unlabelled(session, row, kept)
        row.segments = transcript.dumps(kept)
        log_action(session, "transcribed", "recording", row.id)
        check()
        session.commit()
    finally:
        session.close()


def _named_if_unlabelled(session: Session, row: Recording, segments: list[dict]) -> list[dict]:
    """The model's reading of the words (row 11) only where the voices gave no
    labels: a label from the audio is not second-guessed by the text."""
    if any(seg["speaker"] for seg in segments) or not deps.get_ollama().is_running():
        return segments
    return _named(session, row, segments)


def _people_at(session: Session, row: Recording) -> list[str]:
    """The attendees of the meeting it was recorded into: names the model
    may use, read from the note, never guessed."""
    entry = session.get(Entry, row.entry_id) if row.entry_id else None
    return meeting_shape.attendees(manager_text.readable_content(entry)) if entry else []


def _named(session: Session, row: Recording, segments: list[dict]) -> list[dict]:
    """Row 11: the segments with the model's speaker for each turn, or as
    they were when the model fails (a transcript is never lost to a label)."""
    try:
        return transcript.clean(
            speakers.label(segments, _people_at(session, row), deps.get_model_manager(), deps.get_ollama())
        )
    except Exception:  # noqa: BLE001  # any model failure leaves the lines unlabelled
        logger.warning("naming the speakers failed", exc_info=True)
        return segments


def _segments_of(session: Session, recording_id: int, *, write: bool = False) -> tuple[Recording, list[dict]]:
    row = _writable(session, recording_id) if write else _get(session, recording_id)
    segments = transcript.loads(row.segments)
    if not segments:
        raise HTTPException(status_code=404, detail="That recording has no transcript yet. Transcribe it first.")
    return row, segments


@router.get("/recordings/{recording_id}/transcript")
def read_transcript(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """The transcript's lines with their times, each one a moment the player
    seeks to."""
    _row, segments = _segments_of(session, recording_id)
    return {"segments": segments, "speakers": any(seg["speaker"] for seg in segments), "lines": transcript.to_lines(segments)}


@router.post("/recordings/{recording_id}/speakers")
def name_speakers(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """Name the turns of a transcript made while the model was off (row 11).
    Behind the model gate: with none, 503 and the sentence the menu never
    needs to show, since it offers this only when a model is on."""
    row, segments = _segments_of(session, recording_id, write=True)
    if not deps.get_ollama().is_running():
        raise HTTPException(status_code=503, detail="Naming the speakers needs the local AI, which is off.")
    named = _named(session, row, [{**seg, "speaker": None} for seg in segments])
    row.segments = transcript.dumps(named)
    session.commit()
    return {"segments": named, "speakers": any(seg["speaker"] for seg in named)}


@router.post("/recordings/{recording_id}/speakers/voice", status_code=202)
def label_speakers_by_voice(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """Label who speaks each line from the audio (`ai/diarize.py`), as a
    background run shaped like a transcription: the card shows it, a
    notification says when it ends. It replaces the transcript's speaker
    names, so the page asks first when there are names. Behind the optional
    Speakers bundle: without it, 503 and the sentence that says where."""
    row, _segments = _segments_of(session, recording_id, write=True)
    if not diarize.available():
        raise HTTPException(status_code=503, detail=diarize.INSTALL_HINT)
    path = recordings.path_of(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That recording's audio is missing.")
    token = _acting_for(session, row, path)
    name = row.title or "a recording"
    job = activity.start("transcription", f"Telling the voices apart in “{name}”", stoppable=False)
    if not recordings.begin_transcription(row.id, job.id, task="voices"):
        activity.finish(job)
        raise HTTPException(status_code=409, detail="That recording is already being worked on.")
    work = (row.id, Path(path), session.info.get("workspace_id"), job, token)
    jobs.thread(f"voices-{row.id}", lambda: _label_in_background(*work))
    return {"id": row.id, "job_id": job.id, "transcription": recordings.transcription_of(row.id)}


def _label_in_background(
    recording_id: int, path: Path, workspace: str | None, job: activity.Job, token: str | None = None
) -> None:
    state, error, count = "done", "", 0
    try:
        with sealed_files.for_background(path, token) as (audio, check):
            found = diarize.spans(audio)
            check()
            count = _keep_voice_labels(recording_id, found, workspace, check)
    except RuntimeError as exc:
        logger.warning("telling the voices apart failed: %s", exc)
        state, error = "failed", _sentence(exc, VOICES_FAILED)
    except Exception:  # noqa: BLE001  # a bad clip or a model that will not load is a row that says so
        logger.warning("telling the voices apart failed", exc_info=True)
        state, error = "failed", VOICES_FAILED
    finally:
        _record_failure(job, state, error)
        job.result = {"done": f"{count} speakers", "failed": error}[state]
        activity.finish(job)
        recordings.end_transcription(recording_id, state, error, speakers=count)


def _keep_voice_labels(recording_id: int, found: list, workspace: str | None, check: Callable[[], None] = _open_door) -> int:
    """Write the voices' labels over the transcript; the number of speakers.
    `check` is asked immediately before the commit, as `_keep_segments` does."""
    session = deps.get_db().session()
    if workspace:
        session.info["workspace_id"] = workspace
    try:
        row = session.query(Recording).filter(Recording.id == recording_id).first()
        if row is None:
            raise RunFailed("That recording was deleted while its voices were told apart.")
        segments = transcript.loads(row.segments)
        labels = diarize.voice_labels(segments, found)
        if labels is None:
            return 0
        labelled = transcript.clean([{**seg, "speaker": label} for seg, label in zip(segments, labels, strict=True)])
        count = diarize.speaker_count(labelled)
        row.segments = transcript.dumps(labelled)
        log_action(session, "edited", "recording", row.id, f"{count} speakers labelled by voice")
        check()
        session.commit()
        return count
    finally:
        session.close()


class RenameSpeakerBody(BaseModel):
    from_name: str = Field(min_length=1, max_length=transcript.MAX_SPEAKER)
    to_name: str = Field(max_length=transcript.MAX_SPEAKER)


@router.put("/recordings/{recording_id}/speakers")
def rename_speaker(recording_id: int, body: RenameSpeakerBody, session: Session = Depends(get_session)) -> dict:
    """Rename one speaker everywhere in a transcript (ledger 1514): the model's
    "Speaker A" becomes "Priya", or a wrong guess is corrected. An empty new
    name drops the label from those turns. No model needed."""
    _row, segments = _segments_of(session, recording_id, write=True)
    old = " ".join(body.from_name.split())
    new = " ".join(body.to_name.split()) or None
    if not any(seg["speaker"] == old for seg in segments):
        raise HTTPException(status_code=404, detail="No turn in this transcript has that speaker.")
    renamed = [{**seg, "speaker": new} if seg["speaker"] == old else seg for seg in segments]
    _row.segments = transcript.dumps(renamed)
    log_action(session, "edited", "recording", recording_id, f"speaker {old} renamed")
    session.commit()
    return {"segments": transcript.loads(_row.segments), "speakers": any(seg["speaker"] for seg in renamed)}


def _subtitles(session: Session, recording_id: int, ext: str) -> Response:
    row, segments = _segments_of(session, recording_id)
    body = transcript.to_srt(segments) if ext == "srt" else transcript.to_vtt(segments)
    stem = re.sub(r"[^\w._ -]", "_", row.title or "").strip(". ")[:80] or f"recording-{row.id}"
    name = f"{stem}.{ext}"
    return Response(
        content=body.encode("utf-8"),
        media_type="application/x-subrip" if ext == "srt" else "text/vtt",
        headers=attachment_headers(name),
    )


@router.get("/recordings/{recording_id}/transcript.srt")
def transcript_srt(recording_id: int, session: Session = Depends(get_session)) -> Response:
    return _subtitles(session, recording_id, "srt")


@router.get("/recordings/{recording_id}/transcript.vtt")
def transcript_vtt(recording_id: int, session: Session = Depends(get_session)) -> Response:
    return _subtitles(session, recording_id, "vtt")


def _locked_away(session: Session, recording_id: int) -> bool:
    """A recording hidden only because its private space is locked for this
    caller: 423, so the player says "unlock" rather than "missing". A raw
    statement is not narrowed by the space filter (`database._add_workspace_filter`)."""
    sealed = session.info.get("sealed_workspaces")
    if not sealed:
        return False
    space = session.execute(
        text("SELECT workspace_id FROM recordings WHERE id = :id AND deleted_at IS NULL"), {"id": recording_id}
    ).scalar()
    return space in sealed


@media_router.get("/media/recordings/{recording_id}")
def recording_audio(
    recording_id: int, session: Session = Depends(get_session), range: str | None = Header(default=None)  # noqa: A002
) -> Response:
    try:
        row = _get(session, recording_id)
    except HTTPException as exc:
        if _locked_away(session, recording_id):
            raise HTTPException(status_code=423, detail=sealed_files.LOCKED_DETAIL) from exc
        raise
    path = recordings.path_of(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That recording's audio is missing.")
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
        "Cache-Control": "no-store",
    }
    return sealed_aware(path, media_type=row.mime, headers=headers, request_range=range)

