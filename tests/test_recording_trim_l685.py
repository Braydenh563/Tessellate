"""L685 D18: a wav recording is trimmed on the server into a new wav, the
original kept (same container, no decode in the tab)."""

from __future__ import annotations

import io
import struct
import wave

import pytest

from tessellate.core import deps, recording_trim, recordings
from tessellate.core.database import Recording
from tests._clock import SUITE_NOW, pin_clock

RATE = 1000  # one frame a millisecond keeps the arithmetic readable


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    pin_clock(monkeypatch, SUITE_NOW)


def _wav(frames: int = 2000, channels: int = 1) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", i % 30000) * channels for i in range(frames)))
    return out.getvalue()


def _saved(client, data: bytes, mime="audio/wav", **finish):
    made = client.post("/recordings", json={"title": "Standup", "mime": mime}).json()
    client.post(f"/recordings/{made['id']}/chunk", files={"file": ("c", data, mime)}, data={"duration_ms": "2000"})
    done = client.post(f"/recordings/{made['id']}/finish", json={"duration_ms": 2000, **finish})
    assert done.status_code == 200, done.text
    return done.json()


def _frames(path):
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())


def test_trim_writes_a_new_wav_and_keeps_the_original(client):
    source = _saved(client, _wav(), peaks=list(range(20)), markers=[100, {"at": 700, "note": "key"}, 1500])
    before = recordings.path_of(_row(source["id"])).read_bytes()
    made = client.post(f"/recordings/{source['id']}/trim", json={"start_ms": 500, "end_ms": 1000})
    assert made.status_code == 201, made.text
    body = made.json()
    assert (body["source_id"], body["derived"], body["mime"], body["state"]) == (source["id"], "trim", "audio/wav", "saved")
    assert body["duration_ms"] == 500 and body["title"] == "Standup (trimmed)"
    assert [m["at"] for m in body["marks"]] == [200] and body["marks"][0]["note"] == "key"
    assert body["peaks"] == list(range(5, 10))
    rate, channels, data = _frames(recordings.path_of(_row(body["id"])))
    assert (rate, channels) == (RATE, 1)
    assert data == _frames(recordings.path_of(_row(source["id"])))[2][1000:2000]
    assert recordings.path_of(_row(source["id"])).read_bytes() == before
    again = client.get(f"/recordings/{source['id']}")
    assert again.json()["duration_ms"] == 2000


def test_trim_keeps_stereo_and_clamps_the_end(client):
    source = _saved(client, _wav(channels=2))
    body = client.post(f"/recordings/{source['id']}/trim", json={"start_ms": 1500, "end_ms": 9000}).json()
    assert body["duration_ms"] == 500
    assert _frames(recordings.path_of(_row(body["id"])))[1] == 2


def test_trim_refusals(client):
    source = _saved(client, _wav())
    empty = client.post(f"/recordings/{source['id']}/trim", json={"start_ms": 900, "end_ms": 900})
    past = client.post(f"/recordings/{source['id']}/trim", json={"start_ms": 5000, "end_ms": 6000})
    webm = _saved(client, b"\x1a\x45\xdf\xa3" + b"\x00" * 60, mime="audio/webm")
    other = client.post(f"/recordings/{webm['id']}/trim", json={"start_ms": 0, "end_ms": 10})
    missing = client.post("/recordings/9999/trim", json={"start_ms": 0, "end_ms": 10})
    assert (empty.status_code, past.status_code, other.status_code, missing.status_code) == (400, 400, 415, 404)


def test_a_riff_that_is_not_pcm_is_refused_and_leaves_no_file(client):
    junk = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 40
    source = _saved(client, junk)
    folder = recordings.directory()
    names = set(p.name for p in folder.iterdir())
    refused = client.post(f"/recordings/{source['id']}/trim", json={"start_ms": 0, "end_ms": 10})
    assert refused.status_code == 415
    assert set(p.name for p in folder.iterdir()) == names


def test_cut_streams_in_blocks(tmp_path, monkeypatch):
    path = tmp_path / "a.wav"
    path.write_bytes(_wav(1000))
    monkeypatch.setattr(recording_trim, "BLOCK_FRAMES", 300)
    parts = list(recording_trim.cut(path, 100, 900))
    assert len(parts) == 1 + 3 and len(parts[0]) == 44
    assert b"".join(parts[1:]) == _frames(path)[2][200:1800]


def _row(rid):
    session = deps.get_db().session()
    try:
        row = session.get(Recording, rid)
        session.expunge(row)
        return row
    finally:
        session.close()
