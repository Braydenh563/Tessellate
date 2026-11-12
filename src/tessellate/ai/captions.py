"""Live captions: the page streams microphone audio, a local helper turns
windows of it into text, nothing leaves the machine (WORLD_CLASS_PLAN 28.5
row 9; "Audio in the notebook" decisions 4 and 5).

**The helper is outside the app.** It is whatever answers the whisper.cpp
`whisper-server` dialect (never a Python import here, never a build step in the
suite). `TESSELLATE_CAPTIONS_URL` names one and always wins. Without it, once
Settings, Packages has the Live captions engine and model, the app starts its
own (`ai/captions_helper.py`, run by `ai/captions_process.py`) on the first
`begin()`, never at boot. With neither there are no captions and the status
says so. No test reaches for a real helper: the tests run against
`scratchpad/fake_captions_server.py`, and the ones that need a real model are
marked `captions` and skipped without the URL, the shape of
`TESSELLATE_EVALS_URL`.

**The window is whisper.cpp `stream`'s idea, in our shape.** `stream` (MIT,
ggml authors) samples the microphone itself through SDL; the browser owns the
microphone here, so the page posts 16 kHz mono PCM chunks and this module
keeps the rolling window: every `STEP_MS` of new audio the last `LENGTH_MS`
go to the helper as one WAV, with `audio_ctx` cut to the window (the encoder
otherwise always works a full 30 s; measured 2.25 s to 0.72 s for a 5 s window
on tiny.en, caption82-1010.md). At most one request is in flight: a chunk that
arrives meanwhile only extends the buffer, so latency never queues. A pause, or
a full window, commits the running line and starts the next, so the text a
person has read never moves.

**Audio stays local by construction**: a helper URL that is not on this
machine is refused, because a captions helper on another host would be audio
leaving it.
"""

from __future__ import annotations

import array
import io
import ipaddress
import logging
import os
import secrets
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import requests

from tessellate.ai import captions_process
from tessellate.core import activity

logger = logging.getLogger("tessellate.captions")

SAMPLE_RATE = 16000
BYTES_PER_MS = SAMPLE_RATE * 2 // 1000  # 16-bit mono
#: New audio between two helper calls, and the window each call carries.
STEP_MS = 700
LENGTH_MS = 6000
#: Audio kept when a line commits, so a word cut by the boundary is not lost.
KEEP_MS = 200
#: A pause this long commits the running line.
PAUSE_MS = 800
#: RMS of a 16-bit sample below which a stretch is silence.
SILENCE_RMS = 450.0
#: One chunk from the page is about 250 ms; this is the ceiling, not the norm.
MAX_CHUNK_BYTES = 64 * 1024
#: A session that hears nothing for this long ends and is saved.
IDLE_SECONDS = 60
MAX_TRANSCRIPT_CHARS = 200_000
LAST_LINES = 3
#: Failed helper calls in a row before the session gives up.
MAX_FAILURES = 5

NO_HELPER_HINT = "Live captions need a speech helper. Install Live captions in Settings, Packages."
NOT_LOCAL_HINT = "Live captions only run on this computer, so the helper's address has to be local."

_probe: dict = {"at": 0.0, "url": "", "ok": False}


class CaptionsError(RuntimeError):
    """Something the person can act on; the message is a sentence."""


def _env_url() -> str:
    return os.environ.get("TESSELLATE_CAPTIONS_URL", "").strip().rstrip("/")


def helper_url() -> str:
    """The variable first (nothing is spawned then); else the app's own helper
    if it is running. Never starts one."""
    return _env_url() or captions_process.url()


def model_label() -> str:
    return os.environ.get("TESSELLATE_CAPTIONS_MODEL", "").strip() or "tiny.en"


def _is_local(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _http() -> requests.Session:
    # trust_env off: a proxy in the environment must never carry audio.
    session = requests.Session()
    session.trust_env = False
    return session


def status() -> dict:
    """`voice.status`'s `captions` object. The probe is cached ten seconds so
    the dashboard polling it does not hammer the helper."""
    url = helper_url()
    if not url and not _env_url():
        if captions_process.gave_up():
            return {"available": False, "model": model_label(), "hint": captions_process.STOPPED_HINT}
        if captions_process.installed():
            # Installed, started on first use: ready as far as the page cares.
            return {
                "available": True,
                "model": model_label(),
                "hint": None,
                "starts_on_first_use": True,
                **({"starting": True} if captions_process.starting else {}),
            }
    if not url:
        return {"available": False, "model": model_label(), "hint": NO_HELPER_HINT}
    if not _is_local(url):
        return {"available": False, "model": model_label(), "hint": NOT_LOCAL_HINT}
    ok = _probe["ok"]
    if _probe["url"] != url or time.monotonic() - _probe["at"] > 10:
        try:
            ok = _http().get(url + "/", timeout=1).status_code < 500
        except requests.RequestException:
            ok = False
        _probe.update(at=time.monotonic(), url=url, ok=ok)
    hint = None if ok else "The captions helper isn't answering. Start it, then try again."
    return {"available": ok, "model": model_label(), "hint": hint}


def _rms(pcm: bytes) -> float:
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


def wav_of(pcm: bytes) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return out.getvalue()


def _clean(text: str) -> str:
    """The helper's text without its non-speech markers ([BLANK_AUDIO],
    (music), *sigh*), which are not words and not captions."""
    words = [
        w for w in text.replace("\n", " ").split(" ")
        if w and not (w[0] in "[(*" and w[-1] in "])*")
    ]
    return " ".join(words).strip()


@dataclass
class Session:
    id: str = field(default_factory=lambda: secrets.token_urlsafe(9))
    started: float = field(default_factory=time.monotonic)
    seen: float = field(default_factory=time.monotonic)
    pcm: bytearray = field(default_factory=bytearray)
    #: Milliseconds of audio received in all, and at the last helper call.
    heard_ms: int = 0
    asked_ms: int = 0
    silent_ms: int = 0
    #: Something was said since the last commit, and since the last call.
    voiced: bool = False
    dirty: bool = False
    running: str = ""
    lines: list[str] = field(default_factory=list)
    failures: int = 0
    inflight: bool = False
    stopped: bool = False
    job: activity.Job | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    #: **Keeping the audio** (ledger libr-1011 row 1226), only when the page
    #: asked: every chunk is appended to `spool` (a raw 16 kHz mono file beside
    #: the recordings), and each committed line remembers when it began and
    #: ended, so Stop can write a Recording whose transcript seeks the audio.
    keep_audio: bool = False
    spool: Path | None = None
    line_start: int = 0
    timings: list[tuple[int, int]] = field(default_factory=list)

    def segments(self) -> list[dict]:
        """The lines with their times, for a Recording's transcript: committed
        lines as they were, the one still running ending where the audio does."""
        out = []
        for text, (start, end) in zip(self.lines, self.timings, strict=False):
            out.append({"start": start, "end": max(end, start + 1), "text": text, "speaker": ""})
        if self.running.strip():
            out.append({"start": self.line_start, "end": max(self.heard_ms, self.line_start + 1), "text": self.running, "speaker": ""})
        return out

    def write_wav(self, dest: Path, bins: int = 200) -> tuple[int, list[int]]:
        """The spool as a WAV at `dest`, streamed (an hour is 115 MB), with the
        waveform the Recordings shelf draws. Returns (size in bytes, peaks)."""
        if self.spool is None or not self.spool.is_file():
            return 0, []
        total = self.spool.stat().st_size // 2 * 2
        per_bin = max(2, total // bins // 2 * 2)
        peaks: list[int] = []
        with self.spool.open("rb") as src, wave.open(str(dest), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(SAMPLE_RATE)
            left = total
            while left > 0:
                block = src.read(min(left, per_bin))
                if not block:
                    break
                left -= len(block)
                out.writeframes(block[: len(block) // 2 * 2])
                peaks.append(min(100, int(_rms(block) / 32768 * 100 * 6)))
        return dest.stat().st_size, peaks

    def discard_audio(self) -> None:
        """Drop the spool: Stop without saving, a failure, or after the WAV."""
        if self.spool is not None:
            self.spool.unlink(missing_ok=True)

    def transcript(self) -> str:
        parts = [*self.lines, self.running] if self.running else list(self.lines)
        return "\n".join(parts)[:MAX_TRANSCRIPT_CHARS]

    def view(self, **extra: object) -> dict:
        return {
            "running": self.running,
            "lines": self.lines[-LAST_LINES:],
            #: Committed in all, so the page keeps every line by position.
            "count": len(self.lines),
            "elapsed_ms": self.heard_ms,
            "stopped": self.stopped,
            **extra,
        }

    def _trim(self) -> None:
        del self.pcm[: max(0, len(self.pcm) - KEEP_MS * BYTES_PER_MS)]

    def _commit(self) -> None:
        if self.running:
            self.lines.append(self.running)
            self.timings.append((self.line_start, self.heard_ms))
            self.running = ""
        self._trim()
        self.voiced = False

    def _hear(self, chunk: bytes) -> None:
        """Take a chunk into the window and the silence count (lock held)."""
        self.seen = time.monotonic()
        if self.job is not None:
            self.job.touch()
        self.pcm += chunk
        before = self.heard_ms
        self.heard_ms += len(chunk) // BYTES_PER_MS
        if self.spool is not None:
            with self.spool.open("ab") as out:
                out.write(chunk)
        if _rms(chunk) >= SILENCE_RMS:
            if not self.voiced:
                self.line_start = before
            self.silent_ms = 0
            self.voiced = self.dirty = True
        else:
            self.silent_ms += len(chunk) // BYTES_PER_MS

    def _plan(self) -> tuple[bytes | None, bool]:
        """What to do with the window now (lock held): the audio to send to
        the helper or None, and whether the line closes with this answer."""
        if self.inflight:
            return None, False
        closing = self.silent_ms >= PAUSE_MS or len(self.pcm) >= LENGTH_MS * BYTES_PER_MS
        due = self.dirty and self.heard_ms - self.asked_ms >= STEP_MS
        if not (closing or due):
            return None, False
        if closing and not self.dirty:
            self._commit()  # nothing new since the last answer: just close it
            return None, False
        self.inflight, self.dirty, self.asked_ms = True, False, self.heard_ms
        return bytes(self.pcm[-LENGTH_MS * BYTES_PER_MS :]), closing

    def _settle(self, text: str | None, error: CaptionsError | None, closing: bool) -> dict:
        """Apply the helper's answer (or failure) and answer the page."""
        with self.lock:
            self.inflight = False
            if error is None:
                self.failures = 0
                self.running = text or self.running
            else:
                self.failures += 1
                self.dirty = True  # ask again next step
                if self.failures >= MAX_FAILURES:
                    raise error
                logger.info("captions helper failed (%s)", error)
            if closing:
                self._commit()
            return self.view(**({"error": str(error)} if error else {}))

    def feed(self, chunk: bytes) -> dict:
        """Take one chunk; maybe ask the helper; answer what to show.

        The helper call runs outside the lock, so a chunk that arrives while
        one is out is appended and answered at once (`busy`) instead of
        queueing behind it.
        """
        with self.lock:
            self._hear(chunk)
            if not self.voiced:
                self._trim()
                return self.view()
            busy = self.inflight
            window, closing = self._plan()
            if window is None:
                return self.view(**({"busy": True} if busy else {}))
        try:
            text, error = infer(window, audio_ctx=min(1500, len(window) // BYTES_PER_MS // 20 + 64)), None
        except CaptionsError as exc:
            text, error = None, exc
        return self._settle(text, error, closing)


def infer(pcm: bytes, audio_ctx: int = 0) -> str:
    """One WAV window to the helper's `/inference`; its text, cleaned."""
    url = helper_url() or _own_helper()
    if not url:
        raise CaptionsError(NO_HELPER_HINT)
    if not _is_local(url):
        raise CaptionsError(NOT_LOCAL_HINT)
    try:
        return _post(url, pcm, audio_ctx)
    except requests.ConnectionError as exc:
        if _env_url():
            raise CaptionsError("The captions helper didn't answer.") from exc
        # Our own helper died under this window: the next one restarts it
        # (a bounded number of times, captions_process.MAX_RESTARTS).
        try:
            return _post(captions_process.ensure_started(), pcm, audio_ctx)
        except (captions_process.HelperError, requests.RequestException, ValueError) as again:
            raise CaptionsError("The captions helper didn't answer.") from again
    except (requests.RequestException, ValueError) as exc:
        raise CaptionsError("The captions helper didn't answer.") from exc


def _own_helper() -> str:
    """The app's own helper, started if it has died since `begin()`; "" when
    the variable names one (that one is never ours to start)."""
    if _env_url():
        return ""
    try:
        return captions_process.ensure_started()
    except captions_process.HelperError as exc:
        # HelperError's text is a sentence for the person (checked in
        # test_core_message_wording), so it passes through as written.
        raise CaptionsError(exc.args[0] if exc.args else NO_HELPER_HINT) from exc


def _post(url: str, pcm: bytes, audio_ctx: int) -> str:
    reply = _http().post(
        url + "/inference",
        files={"file": ("window.wav", wav_of(pcm), "audio/wav")},
        data={
            "response_format": "json",
            "temperature": "0.0",
            "no_timestamps": "true",
            "suppress_nst": "true",
            **({"audio_ctx": str(audio_ctx)} if audio_ctx else {}),
        },
        timeout=10,
    )
    reply.raise_for_status()
    return _clean(str(reply.json().get("text", "")))


_sessions: dict[str, Session] = {}
_registry_lock = threading.Lock()


SPOOL_PREFIX = ".captions-"


def _sweep_spools() -> None:
    """A run killed with the app leaves its spool; one a day old is nobody's."""
    from tessellate.core import recordings

    cutoff = time.time() - 24 * 3600
    for stale in recordings.directory().glob(f"{SPOOL_PREFIX}*.pcm"):
        try:
            if stale.stat().st_mtime < cutoff:
                stale.unlink()
        except OSError:
            logger.debug("could not remove a stale captions spool", exc_info=True)


def begin(keep_audio: bool = False) -> Session:
    """A new session, the only one: a second microphone stream would double
    every caption. Raises CaptionsError when the helper is not there.
    `keep_audio` is the page's switch (Settings, General, Microphone)."""
    info = status()
    if not info["available"]:
        raise CaptionsError(info["hint"] or NO_HELPER_HINT)
    _own_helper()  # the first use starts the app's own helper
    session = Session(keep_audio=keep_audio)
    if keep_audio:
        from tessellate.core import recordings

        _sweep_spools()
        session.spool = recordings.directory() / f"{SPOOL_PREFIX}{session.id}.pcm"
    with _registry_lock:
        if _sessions:
            raise CaptionsError("Live captions are already running.")
        _sessions[session.id] = session
    session.job = activity.start(
        "captions",
        "Live captions",
        on_stop=lambda: setattr(session, "stopped", True),
        stoppable=True,
        lease=IDLE_SECONDS,
    )
    return session


def running() -> bool:
    """Is a caption run in progress (the Packages rows wait for it to stop)."""
    with _registry_lock:
        return bool(_sessions)


def get(session_id: str) -> Session | None:
    with _registry_lock:
        return _sessions.get(session_id)


def end(session_id: str) -> Session | None:
    with _registry_lock:
        session = _sessions.pop(session_id, None)
    if session is not None:
        session.stopped = True
        activity.finish(session.job)
        with _registry_lock:
            left = len(_sessions)
        captions_process.session_ended(left)
    return session


def expired() -> list[Session]:
    """Sessions that heard nothing for `IDLE_SECONDS`, removed from the
    registry; the caller saves what they caught."""
    now = time.monotonic()
    with _registry_lock:
        stale = [s for s in _sessions.values() if now - s.seen > IDLE_SECONDS]
    return [s for s in (end(s.id) for s in stale) if s is not None]
