"""L632: a trim is cut on the server (PyAV), so the page no longer decodes the
whole take; the new recording keeps the part, its marks and its original."""

from __future__ import annotations

import array
import io
import math
import wave
from pathlib import Path

import pytest

from tessellate.core import recording_trim, recordings
from tessellate.core.database import Recording

JS = (Path(__file__).resolve().parents[1] / "frontend/js/meetings.js").read_text(encoding="utf-8")
RATE = 8000


def _tone(seconds: float) -> bytes:
    n = int(RATE * seconds)
    samples = array.array("h", (int(12000 * math.sin(i / 20)) for i in range(n)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def _frames(wav: bytes) -> tuple[int, int]:
    with wave.open(io.BytesIO(wav)) as w:
        return w.getnframes(), w.getframerate()


def _saved(client, wav: bytes, markers=None) -> int:
    rid = client.post("/recordings", json={"title": "Talk", "mime": "audio/wav"}).json()["id"]
    client.post(f"/recordings/{rid}/chunk", files={"file": ("t.wav", wav, "audio/wav")}, data={"duration_ms": "4000"})
    client.post(f"/recordings/{rid}/finish", json={"duration_ms": 4000, "peaks": list(range(0, 100, 5)), "markers": markers or []})
    return rid


def test_cut_keeps_only_the_span(tmp_path):
    path = tmp_path / "a.wav"
    path.write_bytes(_tone(4))
    frames, rate = _frames(recording_trim.cut(path, 1000, 3000))
    assert rate == RATE and abs(frames - 2 * RATE) <= 160


def test_cut_without_pyav_still_cuts_a_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(recording_trim, "available", lambda: False)
    path = tmp_path / "a.wav"
    path.write_bytes(_tone(4))
    frames, _ = _frames(recording_trim.cut(path, 500, 1500))
    assert frames == RATE


def test_cut_without_pyav_refuses_other_containers(tmp_path, monkeypatch):
    monkeypatch.setattr(recording_trim, "available", lambda: False)
    path = tmp_path / "a.webm"
    path.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 40)
    with pytest.raises(recording_trim.TrimError, match="voice"):
        recording_trim.cut(path, 0, 1000)


def test_the_route_makes_a_new_recording_from_the_part(client, session):
    rid = _saved(client, _tone(4), markers=[500, 1500, 3500])
    made = client.post(f"/recordings/{rid}/trim", json={"start_ms": 1000, "end_ms": 3000})
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["title"] == "Talk (trimmed)" and body["derived"] == "trim" and body["source_id"] == rid
    assert body["state"] == "saved" and abs(body["duration_ms"] - 2000) <= 20
    assert body["markers"] == [500]  # 1500 - 1000; the others fall outside
    assert len(body["peaks"]) == 10  # the middle half of 20 bars
    row = session.get(Recording, body["id"])
    assert _frames(recordings.path_of(row).read_bytes())[0] > 0
    assert session.get(Recording, rid).deleted_at is None  # the original is kept


def test_the_route_refuses_a_bad_span(client):
    rid = _saved(client, _tone(2))
    backwards = client.post(f"/recordings/{rid}/trim", json={"start_ms": 1500, "end_ms": 1000})
    empty = client.post(f"/recordings/{rid}/trim", json={"start_ms": 0, "end_ms": 0})
    missing = client.post("/recordings/99999/trim", json={"start_ms": 0, "end_ms": 1000})
    assert (backwards.status_code, empty.status_code, missing.status_code) == (422, 422, 404)


def test_the_page_no_longer_decodes_the_take_to_trim():
    start = JS.index("async function trimRecording")
    block = JS[start : JS.index("\n  }\n", start)]
    assert "decodeAudioData" not in block and "recordingWav" not in block
    assert "/trim" in block
