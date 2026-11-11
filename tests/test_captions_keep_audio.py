"""Live captions keep their audio as a Recording when asked (ledger libr-1011
row 1226: "then routes_captions._save attaches the audio and makes the transcript
its text").

Off unless the page says so (Settings, General, Microphone, a per-device switch):
speech is not stored by default. With it on, Stop writes the note and a WAV
Recording whose `entry_id` is the note and whose transcript is the timed lines;
every other ending (Stop without saving, nothing said) leaves no file behind."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from tessellate.ai import captions
from tessellate.core import activity, recordings

from tests.test_captions import CHUNK, fake
from tests import _js_scope
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("TESSELLATE_CAPTIONS_URL", raising=False)
    captions._probe.update(at=0.0, url="", ok=False)
    captions._sessions.clear()
    activity.clear()
    yield
    captions._sessions.clear()
    activity.clear()


@pytest.fixture()
def helper(monkeypatch):
    server = fake.serve()
    monkeypatch.setenv("TESSELLATE_CAPTIONS_URL", f"http://127.0.0.1:{server.server_address[1]}")
    yield server
    server.shutdown()


def _post_all(client, sid, pcm):
    for i in range(0, len(pcm), CHUNK):
        r = client.post(f"/voice/captions/{sid}/audio", content=pcm[i : i + CHUNK])
        assert r.status_code == 200, r.text


def _spools() -> list[Path]:
    return list(recordings.directory().glob(f"{captions.SPOOL_PREFIX}*.pcm"))


def _speech() -> bytes:
    gap = b"\x00\x00" * 16000
    return fake.tone_words([0, 1]) + gap + fake.tone_words([6, 7]) + gap


def test_off_by_default_keeps_no_audio_and_no_file(client, helper):
    sid = client.post("/voice/captions/start", json={}).json()["id"]
    _post_all(client, sid, _speech())
    assert _spools() == []
    done = client.post(f"/voice/captions/{sid}/stop").json()
    assert "recording_id" not in done
    assert client.get("/recordings").json()["recordings"] == []


def test_on_writes_a_recording_pointing_at_the_note_with_timed_lines(client, helper):
    sid = client.post("/voice/captions/start", json={"keep_audio": True}).json()["id"]
    pcm = _speech()
    _post_all(client, sid, pcm)
    assert len(_spools()) == 1
    done = client.post(f"/voice/captions/{sid}/stop").json()
    assert done["entry_id"] and done["recording_id"]
    assert _spools() == [], "the spool goes once the WAV is written"

    rec = client.get(f"/recordings/{done['recording_id']}").json()
    assert rec["state"] == "saved" and rec["mime"] == "audio/wav" and rec["entry_id"] == done["entry_id"]
    assert rec["title"].startswith("Live captions, ")
    assert abs(rec["duration_ms"] - len(pcm) // captions.BYTES_PER_MS) <= 250

    lines = client.get(f"/recordings/{done['recording_id']}/transcript").json()["segments"]
    assert [seg["text"] for seg in lines] == ["hello world", "caption test"]
    assert lines[0]["start"] < lines[0]["end"] <= lines[1]["start"] < lines[1]["end"] <= rec["duration_ms"] + 250

    audio = client.get(f"/media/recordings/{done['recording_id']}")
    assert audio.status_code == 200
    path = recordings.directory() / Path(recordings.path_of(_row(done["recording_id"])).name)
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, captions.SAMPLE_RATE)
        assert w.getnframes() * 1000 // captions.SAMPLE_RATE == len(pcm) // captions.BYTES_PER_MS


def _row(recording_id: int):
    from tessellate.core import deps
    from tessellate.core.database import Recording

    with deps.get_db().session() as session:
        row = session.get(Recording, recording_id)
        session.expunge(row)
        return row


def test_stop_without_saving_drops_the_spool(client, helper):
    sid = client.post("/voice/captions/start", json={"keep_audio": True}).json()["id"]
    _post_all(client, sid, _speech())
    assert len(_spools()) == 1
    done = client.post(f"/voice/captions/{sid}/stop", json={"save": False}).json()
    assert "recording_id" not in done and done["entry_id"] is None
    assert _spools() == []


def test_nothing_said_saves_nothing_and_leaves_no_file(client, helper):
    sid = client.post("/voice/captions/start", json={"keep_audio": True}).json()["id"]
    _post_all(client, sid, b"\x00\x00" * 16000)
    done = client.post(f"/voice/captions/{sid}/stop").json()
    assert done == {"entry_id": None, "text": ""}
    assert _spools() == []
    assert client.get("/recordings").json()["recordings"] == []


def test_a_day_old_spool_is_swept_when_a_run_starts(client, helper):
    import os
    import time

    old = recordings.directory() / f"{captions.SPOOL_PREFIX}old.pcm"
    old.write_bytes(b"\x00\x00")
    os.utime(old, (time.time() - 3 * 86400, time.time() - 3 * 86400))
    sid = client.post("/voice/captions/start", json={"keep_audio": True}).json()["id"]
    assert not old.exists()
    client.post(f"/voice/captions/{sid}/stop", json={"save": False})


def test_the_switch_is_a_device_setting_off_by_default_and_the_page_sends_it():
    root = ROOT / "frontend"
    meetings = unwrapped((root / "js/meetings.js").read_text(encoding="utf-8"))
    captions_js = _js_scope.unwrapped((root / "js/captions.js").read_text(encoding="utf-8"))
    assert '"captionsKeepAudio", "Keep the audio of live captions"' in meetings and ", false],\n];" in meetings
    assert "prefs.bool(key, fallback)" in meetings
    assert 'keep_audio: !opts.stream && prefs.bool("captionsKeepAudio", false)' in captions_js
    assert "and the audio in Recordings" in captions_js
    html = (root / "index.html").read_text(encoding="utf-8")
    assert "Keep the audio of live captions on (Settings, General, Microphone)" in html
