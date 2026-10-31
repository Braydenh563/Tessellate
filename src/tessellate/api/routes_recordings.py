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
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from tessellate.ai import speakers, voice
from tessellate.api import paging
from tessellate.api.downloads import attachment_headers
from tessellate.core import activity, background, deps, recordings, transcript
from tessellate.core.database import LIKE_ESCAPE, Entry, Recording, like_escape, utcnow
from tessellate.core.deps import get_session
from tessellate.entry import bin as other_bin
from tessellate.entry import manager
from tessellate.entry import meetings as meeting_shape
from tessellate.entry.manager import log_action

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
        raise HTTPException(status_code=404, detail="That recording isn't there any more.")
    return row


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
    after finishing any a closed tab left open (row 5): `recovered` lists
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


def _append(path, data: bytes, size: int) -> None:  # noqa: ANN001
    """Append, or leave the file as it was: a write cut short (a full disk)
    is cut back, so the retry starts where the saved audio ends. The error
    goes on to the app's handler, which answers a full disk with 507."""
    try:
        with path.open("ab") as out:
            out.write(data)
    except OSError:
        with path.open("ab") as out:
            out.truncate(size)
        raise


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
    row = _get(session, recording_id)
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
        _append(recordings.path_of(row), data, row.size_bytes)
        row.size_bytes += len(data)
    row.duration_ms = max(row.duration_ms, min(int(duration_ms), 24 * 3600 * 1000))
    row.updated_at = utcnow()
    session.commit()
    return {"id": row.id, "size_bytes": row.size_bytes, "duration_ms": row.duration_ms}


@router.post("/recordings/{recording_id}/finish")
def finish_recording(
    recording_id: int, body: RecordingFinish, session: Session = Depends(get_session)
) -> dict:
    row = _get(session, recording_id)
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


@router.get("/recordings/{recording_id}")
def read_recording(recording_id: int, session: Session = Depends(get_session)) -> dict:
    return recordings.as_dict(_get(session, recording_id))


@router.patch("/recordings/{recording_id}")
def update_recording(
    recording_id: int, body: RecordingPatch, session: Session = Depends(get_session)
) -> dict:
    row = _get(session, recording_id)
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
    row = _get(session, recording_id)
    row.deleted_at = utcnow()
    log_action(session, "binned", "recording", row.id)
    session.commit()
    return {"id": row.id, "binned": True}


@router.post("/recordings/{recording_id}/restore")
def restore_recording(recording_id: int, session: Session = Depends(get_session)) -> dict:
    row = _get(session, recording_id, binned=True)
    row.deleted_at = None
    log_action(session, "restored", "recording", row.id)
    session.commit()
    return recordings.as_dict(row)


@router.post("/recordings/{recording_id}/purge")
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
    row = _get(session, recording_id)
    if not voice.whisper_available():
        raise HTTPException(status_code=503, detail=voice.INSTALL_HINT)
    path = recordings.path_of(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That recording's audio is missing.")
    try:
        with activity.track("transcription", "Transcribing a recording", stoppable=False):
            segments = voice.transcribe_segments(
                Path(path), model_size=deps.get_config().get_preference("voice_model", "base")
            )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # a bad clip must not 500 mysteriously
        logger.warning("transcription failed", exc_info=True)
        raise HTTPException(
            status_code=422, detail="Couldn't transcribe that recording. Try recording it again."
        ) from exc
    kept = transcript.clean(segments)
    if deps.get_ollama().is_running():
        kept = _named(session, row, kept)
    row.segments = transcript.dumps(kept)
    log_action(session, "transcribed", "recording", row.id)
    session.commit()
    return {"text": " ".join(seg["text"] for seg in kept), "segments": kept}


@router.post("/recordings/{recording_id}/transcribe/start", status_code=202)
def start_transcription(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """The same transcription as a background run (UI_MODERNISATION V1): it
    returns at once, closing the dialog or the tab never stops it, the row
    and the running panel show how far it is, and Stop ends it between two
    segments, keeping nothing. 409 while one is already running."""
    row = _get(session, recording_id)
    if not voice.whisper_available():
        raise HTTPException(status_code=503, detail=voice.INSTALL_HINT)
    path = recordings.path_of(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That recording's audio is missing.")
    name = row.title or "a recording"
    job = activity.start("transcription", f"Transcribing “{name}”", stoppable=True)
    if not recordings.begin_transcription(row.id, job.id):
        activity.finish(job)
        raise HTTPException(status_code=409, detail="That recording is already being transcribed.")
    work = (row.id, Path(path), row.duration_ms, deps.get_config().get_preference("voice_model", "base"),
            session.info.get("workspace_id"), job)
    #: Registered (core/background.py, decision 58); the Stop route ends it between
    #: two segments, so the registry entry has no stopper of its own.
    background.start(f"transcribe-{row.id}", lambda: _transcribe_in_background(*work))
    return {"id": row.id, "job_id": job.id, "transcription": recordings.transcription_of(row.id)}


@router.post("/recordings/{recording_id}/transcribe/stop")
def stop_transcription(recording_id: int, session: Session = Depends(get_session)) -> dict:
    _get(session, recording_id)
    run = recordings.transcription_of(recording_id)
    if not run or run.get("state") != "running":
        return {"stopped": False, "detail": "Nothing is transcribing that recording."}
    stopped, detail = activity.stop(run["job_id"])
    return {"stopped": stopped, "detail": detail}


def _transcribe_in_background(
    recording_id: int, path: Path, duration_ms: int, model_size: str, workspace: str | None, job: activity.Job
) -> None:
    kept: list[dict] = []
    state, error = "done", ""
    try:
        for segment in voice.iter_segments(path, model_size=model_size):
            if job.stopped:
                state = "stopped"
                break
            kept.append(segment)
            if duration_ms:
                job.update(done=min(segment["end"], duration_ms), total=duration_ms)
                recordings.note_progress(recording_id, job.progress)
            job.update(detail=f"{len(kept)} lines heard")
        if state == "done" and job.stopped:
            state = "stopped"
        if state == "done":
            _keep_segments(recording_id, kept, workspace)
    except RuntimeError as exc:
        state, error = "failed", str(exc)
    except Exception:  # noqa: BLE001  # a bad clip is a row that says so, never a dead thread
        logger.warning("background transcription failed", exc_info=True)
        state, error = "failed", "Couldn't transcribe that recording. Try recording it again."
    finally:
        words = sum(len(seg["text"].split()) for seg in kept) if state == "done" else 0
        if job.run is not None and state == "failed":
            job.run.fail(error)
        job.result = {"done": f"{words} words", "stopped": "stopped", "failed": error}[state]
        activity.finish(job)
        recordings.end_transcription(recording_id, state, error, words)


def _keep_segments(recording_id: int, segments: list[dict], workspace: str | None) -> None:
    session = deps.get_db().session()
    if workspace:
        session.info["workspace_id"] = workspace
    try:
        row = session.query(Recording).filter(Recording.id == recording_id).first()
        if row is None:
            raise RuntimeError("That recording was deleted while it was transcribed.")
        kept = transcript.clean(segments)
        if deps.get_ollama().is_running():
            kept = _named(session, row, kept)
        row.segments = transcript.dumps(kept)
        log_action(session, "transcribed", "recording", row.id)
        session.commit()
    finally:
        session.close()


def _people_at(session: Session, row: Recording) -> list[str]:
    """The attendees of the meeting it was recorded into: names the model
    may use, read from the note, never guessed."""
    entry = session.get(Entry, row.entry_id) if row.entry_id else None
    return meeting_shape.attendees(manager.readable_content(entry)) if entry else []


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


def _segments_of(session: Session, recording_id: int) -> tuple[Recording, list[dict]]:
    row = _get(session, recording_id)
    segments = transcript.loads(row.segments)
    if not segments:
        raise HTTPException(status_code=404, detail="That recording has no transcript yet. Transcribe it first.")
    return row, segments


@router.get("/recordings/{recording_id}/transcript")
def read_transcript(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """The transcript's lines with their times, each one a moment the player
    seeks to."""
    _row, segments = _segments_of(session, recording_id)
    return {"segments": segments, "speakers": any(seg["speaker"] for seg in segments)}


@router.post("/recordings/{recording_id}/speakers")
def name_speakers(recording_id: int, session: Session = Depends(get_session)) -> dict:
    """Name the turns of a transcript made while the model was off (row 11).
    Behind the model gate: with none, 503 and the sentence the menu never
    needs to show, since it offers this only when a model is on."""
    row, segments = _segments_of(session, recording_id)
    if not deps.get_ollama().is_running():
        raise HTTPException(status_code=503, detail="Naming the speakers needs the local AI, which is off.")
    named = _named(session, row, [{**seg, "speaker": None} for seg in segments])
    row.segments = transcript.dumps(named)
    session.commit()
    return {"segments": named, "speakers": any(seg["speaker"] for seg in named)}


class RenameSpeakerBody(BaseModel):
    from_name: str = Field(min_length=1, max_length=transcript.MAX_SPEAKER)
    to_name: str = Field(max_length=transcript.MAX_SPEAKER)


@router.put("/recordings/{recording_id}/speakers")
def rename_speaker(recording_id: int, body: RenameSpeakerBody, session: Session = Depends(get_session)) -> dict:
    """Rename one speaker everywhere in a transcript (ledger 1514): the model's
    "Speaker A" becomes "Priya", or a wrong guess is corrected. An empty new
    name drops the label from those turns. No model needed."""
    _row, segments = _segments_of(session, recording_id)
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


@media_router.get("/media/recordings/{recording_id}")
def recording_audio(recording_id: int, session: Session = Depends(get_session)) -> FileResponse:
    row = _get(session, recording_id)
    path = recordings.path_of(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That recording's audio is missing.")
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
        "Cache-Control": "no-store",
    }
    return FileResponse(path, media_type=row.mime, headers=headers)

