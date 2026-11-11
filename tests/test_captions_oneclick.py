"""INBOX 1777: live captions installed with one click and run by the app.

The two rows (`captions` the pywhispercpp wheel, `captionmodel` the pinned
tiny.en file), the platform gate, the lazy child process and its life around
the sessions. Every engine here is a fake (the fake captions server as the
child, the fake file server for the download): real whisper.cpp inference on
real speech is unverified by this file.
"""

from __future__ import annotations

import re
import sys
import threading
from pathlib import Path

import pytest

from tessellate.ai import captions, captions_process
from tessellate.core import extra_downloads, extras

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
FAKE = str(ROOT / "scratchpad" / "fake_captions_server.py")
_spec = importlib.util.spec_from_file_location("fake_captions_server", ROOT / "scratchpad" / "fake_captions_server.py")
fake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake)
CHUNK = 250 * captions.BYTES_PER_MS


@pytest.fixture(autouse=True)
def _clean_extras():
    extras.reset_for_tests()
    yield
    extras.reset_for_tests()


# --- the catalogue -----------------------------------------------------------------


def test_the_engine_is_the_pinned_wheel_and_the_model_a_pinned_download():
    engine = extras.EXTRAS_BY_ID["captions"]
    model = extras.EXTRAS_BY_ID["captionmodel"]
    assert engine.packages == ("pywhispercpp==1.5.1",) and engine.module == "pywhispercpp"
    assert engine.kind == "pip" and engine.licence == "MIT"
    assert model.kind == "download" and model.licence == "MIT"
    (download,) = model.downloads
    assert download.url.startswith("https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/")
    assert "/main/" not in download.url, "a commit, so the bytes cannot move"
    assert download.sha256 == "c77c5766f1cef09b6b7d47f21b546cbddd4157886b3b5d6d4f709e91e66c7c2b"
    assert download.size == 32166155 and download.unpack == "file"
    assert download.members == (("", extras.CAPTIONS_MODEL_FILE),)
    assert re.fullmatch(r"[A-Za-z0-9._-]+", extras.CAPTIONS_MODEL_FILE)


def test_the_bundle_installs_both_and_neither_row_says_unavailable_where_a_wheel_exists(monkeypatch):
    bundle = next(b for b in extras.BUNDLES if b.id == "captions")
    assert bundle.extras == ("captions", "captionmodel")
    monkeypatch.setattr(extra_downloads, "platform_key", lambda: "linux-x86_64")
    for extra_id in bundle.extras:
        assert extras.unavailable_reason(extras.EXTRAS_BY_ID[extra_id]) == ""
    assert not any(extra.unavailable for extra in extras.EXTRAS if extra.id in bundle.extras)


@pytest.mark.parametrize("key", ["macos-x86_64", "windows-arm64", "linux-x86_64-musl", "freebsd-amd64"])
def test_a_computer_with_no_wheel_is_told_so_and_both_rows_are_refused(client, monkeypatch, key):
    monkeypatch.setattr(extra_downloads, "platform_key", lambda: key)
    rows = {row["id"]: row for row in client.get("/extras").json()["extras"]}
    for extra_id in ("captions", "captionmodel"):
        assert "No whisper.cpp build for this computer" in rows[extra_id]["unavailable"]
        assert "Voice notes" in rows[extra_id]["unavailable"]
        started, message = extras.start(extra_id)
        assert started is False and "can't be installed here" in message


@pytest.mark.parametrize("key", ["windows-x86_64", "linux-x86_64", "linux-aarch64", "macos-arm64"])
def test_the_four_platforms_with_a_wheel_are_installable(client, monkeypatch, key):
    monkeypatch.setattr(extra_downloads, "platform_key", lambda: key)
    rows = {row["id"]: row for row in client.get("/extras").json()["extras"]}
    assert rows["captions"]["unavailable"] == "" and rows["captionmodel"]["unavailable"] == ""


# --- the child's life around the sessions ---------------------------------------------


@pytest.fixture()
def own_helper(monkeypatch, tmp_path):
    """Both rows 'installed', the fake as the child."""
    model = tmp_path / extras.CAPTIONS_MODEL_FILE
    model.write_bytes(b"x")
    monkeypatch.delenv("TESSELLATE_CAPTIONS_URL", raising=False)
    monkeypatch.setattr(captions_process, "installed", lambda: True)
    monkeypatch.setattr(captions_process, "model_path", lambda: model)
    monkeypatch.setattr(captions_process, "_log_path", lambda: tmp_path / "logs" / "h.log")
    monkeypatch.setattr(captions_process, "_command", lambda m: [sys.executable, FAKE, "--print-port", "--model", str(m)])
    captions._probe.update(at=0.0, url="", ok=False)
    captions._sessions.clear()
    captions_process.reset_for_tests()
    yield
    for sid in list(captions._sessions):
        captions.end(sid)
    captions_process.reset_for_tests()
    captions._sessions.clear()


def _post_all(client, sid, pcm):
    out = []
    for i in range(0, len(pcm), CHUNK):
        r = client.post(f"/voice/captions/{sid}/audio", content=pcm[i : i + CHUNK])
        assert r.status_code == 200, r.text
        out.append(r.json())
    return out


def test_one_start_runs_the_whole_thing_through_the_app_s_own_child(client, own_helper):
    assert captions_process.url() == "", "nothing before the first start"
    status = client.get("/voice/status").json()["captions"]
    assert status["available"] is True and status["starts_on_first_use"] is True
    assert captions_process.url() == ""
    sid = client.post("/voice/captions/start").json()["id"]
    assert captions_process.url().startswith("http://127.0.0.1:")
    _post_all(client, sid, fake.tone_words([2, 3, 4, 5]) + b"\x00\x00" * 16000)
    done = client.post(f"/voice/captions/{sid}/stop").json()
    assert done["text"].split() == ["this", "is", "a", "live"]


def test_an_install_with_the_variable_set_never_starts_a_child(client, own_helper, monkeypatch):
    server = fake.serve()
    try:
        monkeypatch.setenv("TESSELLATE_CAPTIONS_URL", f"http://127.0.0.1:{server.server_address[1]}")
        sid = client.post("/voice/captions/start").json()["id"]
        assert captions_process.url() == "" and captions_process._proc is None
        client.post(f"/voice/captions/{sid}/stop")
    finally:
        server.shutdown()


def test_a_child_killed_mid_session_is_restarted_for_the_next_window(client, own_helper):
    sid = client.post("/voice/captions/start").json()["id"]
    first = captions_process.url()
    captions_process._proc.kill()
    captions_process._proc.wait()
    replies = _post_all(client, sid, fake.tone_words([0, 1]) + b"\x00\x00" * 16000)
    assert captions_process.url() and captions_process.url() != first
    assert replies[-1]["lines"] == ["hello world"]


def test_the_helper_stops_when_its_last_session_ends_after_the_idle_wait(client, own_helper, monkeypatch):
    armed = []
    monkeypatch.setattr(captions_process.threading, "Timer", lambda delay, fn: armed.append(delay) or _NoTimer())
    sid = client.post("/voice/captions/start").json()["id"]
    client.post(f"/voice/captions/{sid}/stop")
    assert armed == [captions_process.IDLE_STOP_SECONDS]
    assert captions_process.url(), "still up inside the wait"


class _NoTimer:
    daemon = False

    def start(self):
        pass

    def cancel(self):
        pass


def test_status_answers_while_a_start_holds_the_lock(own_helper):
    """The dock polls while 'Starting captions' is up: it must not wait for the start."""
    answered = []
    with captions_process._lock:
        worker = threading.Thread(target=lambda: answered.append((captions.status(), captions_process.url())))
        worker.start()
        worker.join(5)
    assert answered and answered[0][0]["available"] is True and answered[0][1] == ""


def test_without_both_rows_start_is_a_sentence_not_a_crash(client, monkeypatch):
    monkeypatch.delenv("TESSELLATE_CAPTIONS_URL", raising=False)
    monkeypatch.setattr(captions_process, "installed", lambda: False)
    reply = client.post("/voice/captions/start")
    assert reply.status_code == 503 and "Live captions" in reply.json()["detail"]


# --- changing the rows while the helper holds them ----------------------------------------


def test_removing_or_reinstalling_a_row_stops_the_helper_first(client, own_helper, monkeypatch):
    sid = client.post("/voice/captions/start").json()["id"]
    client.post(f"/voice/captions/{sid}/stop")
    assert captions_process.url()
    monkeypatch.setattr(extras, "removal_locked", lambda extra: "")
    monkeypatch.setattr(extras, "_dispatch", lambda *args, **kwargs: None)
    ok, _message = extras.remove("captionmodel")
    assert ok is True
    assert captions_process.url() == "" and captions_process._proc is None


def test_a_row_is_not_changed_while_captions_are_running(client, own_helper, monkeypatch):
    sid = client.post("/voice/captions/start").json()["id"]
    for extra_id in ("captions", "captionmodel"):
        ok, message = extras.remove(extra_id)
        assert ok is False and "Stop live captions" in message
    assert captions_process.url(), "the running helper is left alone"
    client.post(f"/voice/captions/{sid}/stop")


def test_the_app_stops_the_helper_when_it_quits(client, own_helper):
    from tessellate.api import app as app_module

    sid = client.post("/voice/captions/start").json()["id"]
    client.post(f"/voice/captions/{sid}/stop")
    assert captions_process.url()
    source = Path(app_module.__file__).read_text(encoding="utf-8")
    after_yield = source.split("async def lifespan(", 1)[1].split("        yield\n", 1)[1]
    assert "captions_process.stop()" in after_yield.split("jobs.shutdown(", 1)[0]
