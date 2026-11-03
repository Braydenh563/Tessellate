"""Live captions (28.5 row 9): the page posts microphone chunks, the app keeps
the window and asks the local helper (`ai/captions.py` says how), and Stop
saves what was said as a note.

Chunked POSTs rather than a WebSocket: the app has no socket route and auth
for one, and a chunk whose reply carries the caption is one round trip per
step through the same lock and CSP as every other call.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from tessellate.ai import captions
from tessellate.api import routes_entries
from tessellate.api.schemas import EntryCreate
from tessellate.core import recordings, transcript
from tessellate.core.database import Recording
from tessellate.core.deps import get_session
from tessellate.entry.manager import log_action

router = APIRouter(prefix="/voice/captions", tags=["voice"])
log = logging.getLogger("tessellate.captions")

TAG = "captions"


def _save(session: captions.Session, db: DbSession) -> dict:
    """The transcript as a note; with the page's switch on, the audio as a
    Recording pointing at it (ledger libr-1011 row 1226), its transcript the
    timed lines. Nothing said, nothing saved (and the spool is dropped)."""
    try:
        text = session.transcript().strip()
        if not text:
            return {"entry_id": None, "text": ""}
        now = datetime.now()
        stamp = f"{now.day} {now:%b %Y, %H:%M}"
        entry = routes_entries.create_entry(
            EntryCreate(content=f"Live captions, {stamp}\n\n{text}", tags=[TAG], defer_filing=True), db
        )
        log_action(db, "captioned", "voice", detail=f"{len(text)} characters")
        recording_id = _keep_audio(session, db, entry.id, stamp)
        db.commit()
        #: Present only when audio was kept, so the old answers are unchanged.
        return {"entry_id": entry.id, "text": text, **({"recording_id": recording_id} if recording_id else {})}
    finally:
        session.discard_audio()


def _keep_audio(session: captions.Session, db: DbSession, entry_id: int, stamp: str) -> int | None:
    """The spool written out as a WAV Recording, or None when audio was not
    asked for or a take had nothing in it. A failure here never costs the note."""
    if not session.keep_audio:
        return None
    mime = "audio/wav"
    name = recordings.new_filename(mime)
    dest = recordings.directory() / name
    try:
        size, peaks = session.write_wav(dest)
        if size <= 44:
            dest.unlink(missing_ok=True)
            return None
        row = Recording(
            title=f"Live captions, {stamp}",
            mime=mime,
            filename=name,
            size_bytes=size,
            duration_ms=session.heard_ms,
            peaks=recordings.clean_peaks(peaks),
            segments=transcript.dumps(transcript.clean(session.segments())),
            entry_id=entry_id,
            state="saved",
        )
        db.add(row)
        db.flush()
        log_action(db, "created", "recording", row.id, detail="live captions")
        return row.id
    except Exception:  # noqa: BLE001 - the note is the record; the audio is the extra
        log.warning("could not keep the audio of the captions", exc_info=True)
        dest.unlink(missing_ok=True)
        return None


class StartBody(BaseModel):
    #: The page's switch (Settings, General, Microphone): keep the audio as a
    #: Recording when Stop saves the note. Off unless asked for.
    keep_audio: bool = False


@router.post("/start")
def start(body: StartBody | None = None, db: DbSession = Depends(get_session)) -> dict:
    for stale in captions.expired():  # an abandoned run is saved, not lost
        _save(stale, db)
    try:
        session = captions.begin(keep_audio=bool(body and body.keep_audio))
    except captions.CaptionsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "id": session.id,
        "model": captions.model_label(),
        "step_ms": captions.STEP_MS,
        "sample_rate": captions.SAMPLE_RATE,
    }


@router.post("/{session_id}/audio")
async def audio(session_id: str, request: Request, db: DbSession = Depends(get_session)) -> dict:
    session = captions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Live captions already ended.")
    if int(request.headers.get("content-length") or 0) > captions.MAX_CHUNK_BYTES:
        raise HTTPException(status_code=413, detail="That audio chunk is too large.")
    chunk = await request.body()
    if len(chunk) > captions.MAX_CHUNK_BYTES:
        raise HTTPException(status_code=413, detail="That audio chunk is too large.")
    try:
        return await run_in_threadpool(session.feed, chunk[: len(chunk) // 2 * 2])
    except captions.CaptionsError as exc:
        # The helper failed several times running: end the run, keep the text.
        captions.end(session_id)
        await run_in_threadpool(_save, session, db)  # SQLite off the event loop (audit 1028 K29)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class StopBody(BaseModel):
    #: False when the words were a live view of something kept elsewhere (the
    #: recorder's live transcript, UI_MODERNISATION V5): nothing is saved.
    save: bool = True


@router.post("/{session_id}/stop")
def stop(session_id: str, body: StopBody | None = None, db: DbSession = Depends(get_session)) -> dict:
    session = captions.end(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Live captions already ended.")
    if body is not None and not body.save:
        session.discard_audio()
        return {"entry_id": None, "text": session.transcript().strip()}
    return _save(session, db)
