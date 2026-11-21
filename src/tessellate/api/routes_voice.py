"""Voice capture endpoints: the browser records, the server
transcribes with local Whisper, nothing is sent anywhere.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import captions, diarize, natural_voice, voice
from tessellate.core import activity, deps
from tessellate.api.this_computer import this_computer_only
from tessellate.core.deps import get_session
from tessellate.entry.manager import log_action

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # a spoken note, not a podcast


@router.get("/status")
def status() -> dict:
    available = voice.whisper_available()
    return {
        "available": available,
        "model": deps.get_config().get_preference("voice_model", "base"),
        #: Which sizes are downloaded (B61): Settings marks them and offers to
        #: remove one. A size is fetched at its first dictation, not on choosing.
        "models": voice.model_states(),
        "hint": None if available else voice.INSTALL_HINT,
        #: Live captions are a separate optional helper (decision 5), so they
        #: have their own availability, model and hint.
        "captions": captions.status(),
        #: The translator's row waits for this (WORLD_CLASS_PLAN 28.5 row 10,
        #: Brief 83): shown only once true, so no control does nothing.
        "translate": False,
        #: Speaker labels by voice are ready (the Speakers bundle is installed):
        #: the recordings menu runs them, or points to Settings, Packages.
        "speakers_by_voice": diarize.available(),
        #: The natural voice (Piper, Settings, Packages): `available` is true only with the
        #: engine and the voice both on disk; the page falls back to the browser's voices.
        "speak": natural_voice.status(),
    }


class SpeakIn(BaseModel):
    text: str = Field(max_length=natural_voice.MAX_CHARS * 4)


@router.post("/speak")
def speak(body: SpeakIn) -> Response:
    """Read `body.text` aloud in the natural voice: a wav, made on this computer, kept nowhere."""
    if not natural_voice.available():
        raise HTTPException(status_code=503, detail=natural_voice.INSTALL_HINT)
    try:
        wav = natural_voice.speak(body.text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return Response(wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.delete("/models/{size}", dependencies=[Depends(this_computer_only)])
def remove_model(size: str) -> dict:
    """Delete one downloaded dictation size, by its allowlist name."""
    if size not in voice.WHISPER_SIZES:
        raise HTTPException(status_code=404, detail="No such dictation model.")
    removed, message = voice.remove_model(size)
    if not removed:
        raise HTTPException(status_code=404 if "isn't on this computer" in message else 500, detail=message)
    return {"removed": True, "message": message}


def _transcribe_upload(
    file: UploadFile, session: Session, max_bytes: int, over_limit_detail: str
) -> dict:
    if not voice.whisper_available():
        raise HTTPException(status_code=503, detail=voice.INSTALL_HINT)

    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=over_limit_detail)
    if not data:
        raise HTTPException(status_code=400, detail="The recording is empty.")

    # Only a plain extension of the upload's name reaches the temp file's name (CodeQL path injection).
    suffix = Path(file.filename or "").suffix.lower()
    suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,7}", suffix) else ".webm"
    # delete=True keeps the file open under this handle for the `with` block's
    # whole lifetime: harmless on POSIX, where a second handle can open
    # the same path, but Windows locks a file exclusively while any handle on
    # it is open. faster-whisper's own reader opening that path for decoding
    # then failed with "Permission denied" on every Windows machine, which
    # this sandbox is not, so nothing here had ever seen it fail. Closed by
    # hand and cleaned up in `finally` instead, so nothing holds it open while
    # `voice.transcribe` reads it.
    clip = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        clip.write(data)
        clip.close()
        try:
            #: Listed in Activity; one Whisper call has no step to stop at.
            with activity.track("transcription", "Transcribing a recording", stoppable=False):
                text = voice.transcribe(
                    Path(clip.name),
                    model_size=deps.get_config().get_preference("voice_model", "base"),
                )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:  # a bad clip must not 500 mysteriously
            logging.getLogger("tessellate.voice").warning("transcription failed", exc_info=True)
            raise HTTPException(
                status_code=422,
                detail="Couldn't transcribe that recording. Try recording it again.",
            ) from exc
    finally:
        Path(clip.name).unlink(missing_ok=True)

    log_action(session, "transcribed", "voice", detail=f"{len(data)} bytes")
    session.commit()
    return {"text": text}


@router.post("/transcribe")
def transcribe(file: UploadFile, session: Session = Depends(get_session)) -> dict:
    return _transcribe_upload(
        file, session, MAX_AUDIO_BYTES, "That recording is larger than 25 MB."
    )
