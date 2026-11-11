"""The live-captions helper: a tiny local HTTP server around whisper.cpp.

Run by the app as a child process (`ai/captions_process.py`), never imported
by it (decision 4: the app does not import a speech engine):

    python -m tessellate.ai.captions_helper --model PATH --threads N

It speaks the one dialect `ai/captions.py` uses, whisper.cpp `whisper-server`'s:

  GET  /            200 (the probe)
  POST /inference   multipart `file` (a 16-bit mono 16 kHz WAV) plus the form
                    fields `audio_ctx`, `no_timestamps`, `temperature`,
                    `suppress_nst`; answers `{"text": "..."}`

It binds 127.0.0.1 only, on port 0, and prints the port as its first stdout
line, so the parent never races a fixed port. One lock and one loaded model:
a second request waits (the app sends at most one at a time anyway).

The model is always an absolute path to a file that exists. Given a bare name
pywhispercpp would fetch it from Hugging Face, and a download is the
installer's job (pinned and checked), so a missing file is refused here.

The engine is `pywhispercpp` (whisper.cpp compiled in, MIT). Everything else
is the standard library, so the dialect is tested with a fake transcriber and
the suite never imports the engine.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import threading
import wave
from collections.abc import Callable
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY = 4 * 1024 * 1024  # a 6 s window is 192 KB; this is the ceiling

#: (pcm as 16-bit mono bytes, audio_ctx, options) -> text
Transcribe = Callable[[bytes, int, dict], str]


def _form(body: bytes, content_type: str) -> tuple[bytes, dict[str, str]]:
    """The `file` part and the text fields of a multipart body."""
    message = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1", "replace") + b"\r\n\r\n" + body
    )
    audio, fields = b"", {}
    if not message.is_multipart():
        return audio, fields
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        payload = part.get_payload(decode=True) or b""
        if name == "file":
            audio = payload
        elif name:
            fields[str(name)] = payload.decode("utf-8", "replace").strip()
    return audio, fields


def pcm_of(wav_bytes: bytes) -> bytes:
    """The samples of a 16-bit mono WAV; anything else is a ValueError."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            if w.getsampwidth() != 2 or w.getnchannels() != 1:
                raise ValueError("expected 16-bit mono audio")
            return w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError("not a WAV file") from exc


def _flag(value: str | None, default: bool) -> bool:
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


def make_server(transcribe: Transcribe, port: int = 0) -> ThreadingHTTPServer:
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # the parent logs, not each request
            pass

        def _send(self, code: int, body: bytes, kind: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            self._send(200, b"<html><body>Tessellate captions helper</body></html>", "text/html")

        def do_POST(self) -> None:  # noqa: N802
            if self.path.split("?")[0] != "/inference":
                self._send(404, b'{"error": "not found"}')
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                self._send(413 if length > MAX_BODY else 400, b'{"error": "bad size"}')
                return
            body = self.rfile.read(length)
            try:
                wav_bytes, fields = _form(body, self.headers.get("Content-Type", ""))
                pcm = pcm_of(wav_bytes)
                audio_ctx = int(fields.get("audio_ctx") or 0)
                options = {
                    "no_timestamps": _flag(fields.get("no_timestamps"), True),
                    "suppress_nst": _flag(fields.get("suppress_nst"), True),
                    "temperature": float(fields.get("temperature") or 0.0),
                }
            except ValueError as exc:
                self._send(400, json.dumps({"error": str(exc)}).encode())
                return
            try:
                with lock:
                    text = transcribe(pcm, max(0, audio_ctx), options)
            except Exception as exc:  # noqa: BLE001  # the engine's failure is a 500, not a dead helper
                print(f"inference failed: {type(exc).__name__}", file=sys.stderr, flush=True)
                self._send(500, json.dumps({"error": "inference failed"}).encode())
                return
            self._send(200, json.dumps({"text": text}).encode())

    # 127.0.0.1 only, always: audio never leaves this computer.
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def engine_transcriber(model_path: str, threads: int) -> Transcribe:
    """The real transcriber (imports the engine, so only the process does)."""
    import numpy as np
    from pywhispercpp.model import Model

    model = Model(model_path, n_threads=threads, print_realtime=False, print_progress=False)

    def run(pcm: bytes, audio_ctx: int, options: dict) -> str:
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        # Every call sets audio_ctx: pywhispercpp keeps overrides between calls.
        segments = model.transcribe(
            samples,
            audio_ctx=audio_ctx,
            no_timestamps=options["no_timestamps"],
            suppress_nst=options["suppress_nst"],
            temperature=options["temperature"],
        )
        return " ".join(s.text.strip() for s in segments).strip()

    return run


def _watch_stdin() -> None:
    """Block until the parent closes our stdin (or dies), then exit."""
    try:
        while sys.stdin.read(4096):
            pass
    except (OSError, ValueError):
        pass
    os._exit(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tessellate live-captions helper")
    parser.add_argument("--model", required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument(
        "--exit-on-stdin-close",
        action="store_true",
        help="exit when the parent goes away (the app holds our stdin open)",
    )
    args = parser.parse_args(argv)
    model = Path(args.model)
    if not model.is_absolute() or not model.is_file():
        print("the model must be an absolute path to a file that exists", file=sys.stderr)
        return 2
    try:
        transcribe = engine_transcriber(str(model), max(1, args.threads))
    except ImportError:
        print("pywhispercpp is not installed", file=sys.stderr)
        return 3
    server = make_server(transcribe, 0)
    print(server.server_address[1], flush=True)
    if args.exit_on_stdin_close:
        threading.Thread(target=_watch_stdin, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
