"""The captions helper (`ai/captions_helper.py`) speaks the whisper.cpp server dialect.

The engine is replaced by a fake transcriber, so the suite never imports
pywhispercpp and never loads a model (CLAUDE.md section 4). What a real
`tiny.en` does with real speech is unverified here: see
`tests/test_captions_live.py`, skipped without `TESSELLATE_CAPTIONS_URL`.
"""

from __future__ import annotations

import io
import subprocess
import sys
import threading
import wave
from pathlib import Path

import pytest
import requests

from tessellate.ai import captions, captions_helper

ROOT = Path(__file__).resolve().parents[1]


def _wav(samples: int = 1600) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x01\x00" * samples)
    return buffer.getvalue()


def _http() -> requests.Session:
    session = requests.Session()
    session.trust_env = False  # loopback, never a proxy
    return session


@pytest.fixture()
def served():
    calls: list[tuple[int, int, dict]] = []

    def transcribe(pcm: bytes, audio_ctx: int, options: dict) -> str:
        calls.append((len(pcm), audio_ctx, options))
        return "hello there"

    server = captions_helper.make_server(transcribe)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", calls, _http()
    server.shutdown()
    server.server_close()


def test_it_binds_loopback_only_on_a_free_port():
    server = captions_helper.make_server(lambda *_: "")
    try:
        host, port = server.server_address[:2]
        assert host == "127.0.0.1" and port > 0
    finally:
        server.server_close()


def test_get_root_is_the_probe(served):
    url, _calls, http = served
    assert http.get(url + "/", timeout=5).status_code == 200


def test_the_app_posts_the_way_captions_does_and_gets_text_back(served):
    """`captions._post` builds this exact multipart body; the helper reads it."""
    url, calls, _http_ = served
    text = captions._post(url, b"\x01\x00" * 1600, 750)
    assert text == "hello there"
    assert calls == [(3200, 750, {"no_timestamps": True, "suppress_nst": True, "temperature": 0.0})]


def test_audio_ctx_defaults_to_zero_and_flags_are_read(served):
    url, calls, http = served
    reply = http.post(
        url + "/inference",
        files={"file": ("w.wav", _wav(), "audio/wav")},
        data={"no_timestamps": "false", "temperature": "0.2"},
        timeout=5,
    )
    assert reply.json() == {"text": "hello there"}
    assert calls[-1][1] == 0
    assert calls[-1][2] == {"no_timestamps": False, "suppress_nst": True, "temperature": 0.2}


@pytest.mark.parametrize(
    "files",
    [
        {"file": ("w.wav", b"not a wav", "audio/wav")},
        {"other": ("w.wav", _wav(), "audio/wav")},
    ],
)
def test_a_bad_upload_is_a_400_not_a_dead_helper(served, files):
    url, calls, http = served
    assert http.post(url + "/inference", files=files, timeout=5).status_code == 400
    assert calls == []
    assert http.get(url + "/", timeout=5).status_code == 200


def test_stereo_audio_is_refused():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 40)
    with pytest.raises(ValueError, match="16-bit mono"):
        captions_helper.pcm_of(buffer.getvalue())


def test_other_paths_and_oversize_bodies_are_refused(served):
    url, _calls, http = served
    assert http.post(url + "/other", data=b"x", timeout=5).status_code == 404
    big = b"x" * (captions_helper.MAX_BODY + 1)
    assert http.post(url + "/inference", data=big, timeout=5).status_code == 413


def test_an_engine_failure_is_a_500_and_the_helper_keeps_serving():
    def boom(*_args):
        raise RuntimeError("path /secret/model.bin is broken")

    server = captions_helper.make_server(boom)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    http = _http()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        reply = http.post(url + "/inference", files={"file": ("w.wav", _wav(), "audio/wav")}, timeout=5)
        assert reply.status_code == 500
        assert "secret" not in reply.text, "the engine's message can carry a path"
        assert http.get(url + "/", timeout=5).status_code == 200
    finally:
        server.shutdown()
        server.server_close()


def test_one_request_at_a_time_reaches_the_engine():
    """One loaded model, one lock: two windows never run inside it at once."""
    inside, worst = [0], [0]
    gate = threading.Lock()

    def slow(*_args):
        with gate:
            inside[0] += 1
            worst[0] = max(worst[0], inside[0])
        threading.Event().wait(0.05)
        with gate:
            inside[0] -= 1
        return "x"

    server = captions_helper.make_server(slow)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"

    def hit():
        _http().post(url + "/inference", files={"file": ("w.wav", _wav(), "audio/wav")}, timeout=10)

    threads = [threading.Thread(target=hit) for _ in range(4)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        assert worst[0] == 1
    finally:
        server.shutdown()
        server.server_close()


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603  # fixed args, the test's own interpreter
        [sys.executable, "-m", "tessellate.ai.captions_helper", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )


def test_a_model_that_is_not_an_absolute_existing_file_is_refused(tmp_path):
    """A bare name would make the engine fetch from Hugging Face: the installer's
    pinned, checked download is the only way a model arrives."""
    for model in ("ggml-tiny.en.bin", str(tmp_path / "missing.bin")):
        ran = _run("--model", model)
        assert ran.returncode == 2 and "absolute path" in ran.stderr
        assert ran.stdout == ""


def test_the_helper_exits_when_the_app_closes_its_stdin(tmp_path):
    """A hard-killed app must not leave the helper (and its loaded model) behind:
    the parent holds our stdin open and its death closes it."""
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")
    code = (
        "from tessellate.ai import captions_helper as h;"
        "h.engine_transcriber = lambda *_: (lambda pcm, ctx, opts: 'x');"
        f"raise SystemExit(h.main(['--model', {str(model)!r}, '--exit-on-stdin-close']))"
    )
    proc = subprocess.Popen(  # noqa: S603  # fixed args, the test's own interpreter
        [sys.executable, "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src")},
    )
    try:
        port = int(proc.stdout.readline())
        assert _http().get(f"http://127.0.0.1:{port}/", timeout=5).status_code == 200
        proc.stdin.close()
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()


def test_without_the_engine_it_says_so_and_exits(tmp_path):
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")
    ran = _run("--model", str(model))
    assert ran.returncode != 0 and not ran.stdout.strip().isdigit()
    if "pywhispercpp is not installed" in ran.stderr:
        assert ran.returncode == 3
