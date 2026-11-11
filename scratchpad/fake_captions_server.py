#!/usr/bin/env python3
"""A stdlib stand-in for whisper.cpp's `whisper-server`, for live captions.

**Why this exists.** CLAUDE.md section 4: nothing in the suite may need a real
speech model, and no mode of `scripts/gate.sh` may reach for a helper. The
captions code (`ai/captions.py`) talks to whatever answers at
`TESSELLATE_CAPTIONS_URL`; this is the same shape as `fake_openai_server.py`
for the chat: a real `http.server` on a real port that speaks the one dialect
the app uses, so the sliding window, the commit rule and the route are
exercised end to end without a model.

  GET  /            200, a page (whisper-server serves one; it is the probe)
  POST /inference   multipart `file` (a 16-bit mono WAV) plus optional form
                    fields (`audio_ctx`, `response_format`, ...): answers
                    `{"text": "..."}`
  POST /config?delay_ms=N   change --delay-ms while running (a sweep does)
  GET  /stats       how many inferences ran and the form fields of the last
                    (a test reads it; the real server has no such route)

**What it "recognises".** It is a fake, so the words are in the audio: a
voiced stretch (a tone burst, 20 ms frames above an energy floor) is one word,
and the word is chosen by the burst's pitch, estimated from its zero
crossings: 300 Hz is word 0, 400 Hz word 1, and so on up `VOCAB`. A window
that holds bursts 2 to 5 answers words 2 to 5, a window that slid past burst 2
no longer says it, which is the behaviour the app's window handling has to
live with and what a constant canned reply could never test.
`scratchpad/captions_audio.py` writes such a file (for Chromium's fake
microphone) and `tone_words` is what the tests use.

`--delay-ms` (or FAKE_CAPTIONS_DELAY_MS) sleeps before answering to stand in
for inference time (the measured tiny.en figure in
docs/roadmap/agent-remaining/caption82-1010.md); `--fail-every N` answers 500
to every Nth request, for the failure path.

Run it:  python3 scratchpad/fake_captions_server.py --port 8178
Point the app at it:  TESSELLATE_CAPTIONS_URL=http://127.0.0.1:8178
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VOCAB = [
    "hello", "world", "this", "is", "a", "live", "caption", "test",
    "of", "the", "notebook", "speech", "stays", "on", "this", "machine",
]
BASE_HZ = 300
STEP_HZ = 100
FRAME = 320  # 20 ms at 16 kHz
FLOOR = 600.0  # RMS of 16-bit samples that counts as voiced
MIN_FRAMES = 6  # a burst shorter than 120 ms is a click, not a word


def word_for(freq_hz: float) -> str:
    index = max(0, round((freq_hz - BASE_HZ) / STEP_HZ))
    return VOCAB[index % len(VOCAB)]


def recognise(samples: list[int]) -> str:
    """Words for the voiced bursts in a mono 16 kHz sample list."""
    words: list[str] = []
    run: list[int] = []

    def flush() -> None:
        if len(run) // FRAME < MIN_FRAMES:
            return
        crossings = sum(1 for a, b in zip(run, run[1:]) if (a < 0) != (b < 0))
        seconds = len(run) / 16000
        words.append(word_for(crossings / 2 / seconds))

    for start in range(0, len(samples) - FRAME + 1, FRAME):
        frame = samples[start : start + FRAME]
        rms = (sum(s * s for s in frame) / FRAME) ** 0.5
        if rms >= FLOOR:
            run.extend(frame)
        else:
            if run:
                flush()
            run = []
    if run:
        flush()
    return " ".join(words)


def read_wav(data: bytes) -> list[int]:
    with wave.open(io.BytesIO(data), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != 16000:
            raise ValueError("expected 16 kHz mono 16-bit")
        raw = w.readframes(w.getnframes())
    return [int.from_bytes(raw[i : i + 2], "little", signed=True) for i in range(0, len(raw) - 1, 2)]


def _parts(body: bytes, content_type: str) -> dict[str, bytes]:
    """The fields of a multipart/form-data body (the stdlib parser is gone in
    3.13, and this is a test double, so a small reader is enough)."""
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type)
    if not match:
        return {}
    boundary = (match.group(1) or match.group(2)).encode()
    fields: dict[str, bytes] = {}
    for chunk in body.split(b"--" + boundary):
        head, sep, rest = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        name = re.search(rb'name="([^"]+)"', head)
        if name:
            fields[name.group(1).decode()] = rest[:-2] if rest.endswith(b"\r\n") else rest
    return fields


class Handler(BaseHTTPRequestHandler):
    delay = 0.0
    fail_every = 0
    lock = threading.Lock()
    count = 0
    last: dict = {}

    def log_message(self, *_args) -> None:  # quiet
        pass

    def _send(self, code: int, body: bytes, kind: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/stats":
            with Handler.lock:
                self._send(200, json.dumps({"count": Handler.count, "last": Handler.last}).encode())
        else:
            self._send(200, b"<html><body>fake whisper server</body></html>", "text/html")

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/config"):  # a sweep changes the stand-in delay
            m = re.search(r"delay_ms=([0-9.]+)", self.path)
            Handler.delay = float(m.group(1)) / 1000 if m else 0.0
            self._send(200, b"{}")
            return
        if self.path != "/inference":
            self._send(404, b'{"error":"not found"}')
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        with Handler.lock:
            Handler.count += 1
            n = Handler.count
        fields = _parts(body, self.headers.get("Content-Type", ""))
        with Handler.lock:
            Handler.last = {k: v.decode("latin-1")[:40] for k, v in fields.items() if k != "file"}
        if Handler.fail_every and n % Handler.fail_every == 0:
            self._send(500, b'{"error":"fake failure"}')
            return
        try:
            samples = read_wav(fields.get("file", b""))
        except Exception:  # noqa: BLE001  # a bad upload is a 400, as the real one
            self._send(400, b'{"error":"failed to read audio"}')
            return
        if Handler.delay:
            time.sleep(Handler.delay)
        self._send(200, json.dumps({"text": " " + recognise(samples)}).encode())


def serve(port: int = 0, delay_ms: float = 0.0, fail_every: int = 0) -> ThreadingHTTPServer:
    """Start on `port` (0 = any free one) in a daemon thread; the tests call
    this in-process, so nothing is a subprocess and nothing outlives them."""
    Handler.delay = delay_ms / 1000
    Handler.fail_every = fail_every
    Handler.count = 0
    Handler.last = {}
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def tone_words(indexes: list[int], word_ms: int = 400, gap_ms: int = 300, lead_ms: int = 0) -> bytes:
    """16-bit mono 16 kHz PCM (little-endian) of one tone burst per word
    index, a gap between."""
    import math
    from array import array

    out = array("h", [0] * (16000 * lead_ms // 1000))
    for i in indexes:
        hz = BASE_HZ + STEP_HZ * i
        out.extend(int(9000 * math.sin(2 * math.pi * hz * n / 16000)) for n in range(16000 * word_ms // 1000))
        out.extend([0] * (16000 * gap_ms // 1000))
    if sys.byteorder == "big":
        out.byteswap()
    return out.tobytes()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8178)
    ap.add_argument("--delay-ms", type=float, default=float(os.environ.get("FAKE_CAPTIONS_DELAY_MS", "0")))
    ap.add_argument("--fail-every", type=int, default=0)
    #: The supervisor's child contract (ai/captions_process.py): the port is the
    #: first stdout line. The other flags are the real helper's, ignored here.
    ap.add_argument("--print-port", action="store_true")
    ap.add_argument("--never-answer", action="store_true", help="print a port nothing listens on")
    ap.add_argument("--exit-after", type=float, default=0.0, help="exit this many seconds after starting")
    ap.add_argument("--model", default="")
    ap.add_argument("--threads", default="")
    ap.add_argument("--exit-on-stdin-close", action="store_true")
    args = ap.parse_args()
    #: As the real helper: asked to print its port, it binds any free one.
    server = serve(0 if args.print_port else args.port, args.delay_ms, args.fail_every)
    if args.never_answer:
        server.shutdown()
        server.server_close()
    if args.print_port:
        print(server.server_address[1], flush=True)
    else:
        print(f"fake captions helper on http://127.0.0.1:{server.server_address[1]}", flush=True)
    if args.exit_after:
        time.sleep(args.exit_after)
        sys.exit(1)
    threading.Event().wait()


if __name__ == "__main__":
    main()
