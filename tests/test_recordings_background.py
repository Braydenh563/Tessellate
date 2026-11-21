"""Transcription as a background run (UI_MODERNISATION V1, INBOX 828): the
owner, "if I close it, can I leave it in running in the background ... can I
get a notification when it is done?? also can I stop it". Starting returns at
once; the recording carries the run's state and progress; Stop ends it at the
next segment and keeps nothing; a failure says why. Every case runs against a
stubbed transcriber: faster-whisper is not installed here (CLAUDE.md 4)."""

from __future__ import annotations

import threading

from tessellate.ai import voice
from tessellate.core import activity, recordings

WEBM_HEAD = b"\x1a\x45\xdf\xa3" + b"\x00" * 60
SEGMENTS = [
    {"start": 0, "end": 4000, "text": "First line."},
    {"start": 4000, "end": 9000, "text": "Second line."},
]


def _saved(client, duration_ms=9000):
    made = client.post("/recordings", json={"title": "Standup", "mime": "audio/webm"}).json()
    client.post(
        f"/recordings/{made['id']}/chunk",
        files={"file": ("c.webm", WEBM_HEAD, "audio/webm")},
        data={"duration_ms": str(duration_ms)},
    )
    client.post(f"/recordings/{made['id']}/finish", json={"duration_ms": duration_ms})
    return made["id"]


def test_start_returns_at_once_and_the_recording_carries_the_result(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "iter_segments", lambda path, model_size="base": iter(SEGMENTS))
    rid = _saved(client)
    response = client.post(f"/recordings/{rid}/transcribe/start")
    assert response.status_code == 202, response.text
    assert response.json()["transcription"]["state"] in {"running", "done"}
    assert recordings.wait_transcription(rid, 5)
    body = client.get(f"/recordings/{rid}").json()
    assert body["transcribed"] is True
    assert body["transcription"]["state"] == "done" and body["transcription"]["words"] == 4
    lines = client.get(f"/recordings/{rid}/transcript").json()["segments"]
    assert [line["text"] for line in lines] == ["First line.", "Second line."]


def test_stop_ends_it_at_the_next_segment_and_keeps_nothing(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    first_out = threading.Event()
    go_on = threading.Event()

    def slow(path, model_size="base"):
        yield SEGMENTS[0]
        first_out.set()
        go_on.wait(5)
        yield SEGMENTS[1]

    monkeypatch.setattr(voice, "iter_segments", slow)
    rid = _saved(client)
    job_id = client.post(f"/recordings/{rid}/transcribe/start").json()["job_id"]
    assert first_out.wait(5)
    running = client.get(f"/recordings/{rid}").json()["transcription"]
    assert running["state"] == "running" and 0.4 < running["progress"] < 0.5
    assert any(row["id"] == job_id and row["stoppable"] for row in activity.snapshot())
    stop = client.post(f"/recordings/{rid}/transcribe/stop")
    assert stop.status_code == 200
    go_on.set()
    assert recordings.wait_transcription(rid, 5)
    body = client.get(f"/recordings/{rid}").json()
    assert body["transcription"]["state"] == "stopped" and body["transcribed"] is False


def test_a_failure_says_why_and_a_second_start_is_refused_while_running(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    hold = threading.Event()

    def broken(path, model_size="base"):
        hold.wait(5)
        raise voice.SpeechError("Couldn't load the speech model.")
        yield  # pragma: no cover

    monkeypatch.setattr(voice, "iter_segments", broken)
    rid = _saved(client)
    first = client.post(f"/recordings/{rid}/transcribe/start")
    second = client.post(f"/recordings/{rid}/transcribe/start")
    assert (first.status_code, second.status_code) == (202, 409)
    hold.set()
    assert recordings.wait_transcription(rid, 5)
    run = client.get(f"/recordings/{rid}").json()["transcription"]
    assert run["state"] == "failed" and run["error"] == "Couldn't load the speech model."


def test_no_addon_is_the_install_hint_not_a_run(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: False)
    rid = _saved(client)
    response = client.post(f"/recordings/{rid}/transcribe/start")
    assert response.status_code == 503
    body = client.get(f"/recordings/{rid}").json()
    assert body["transcription"] is None
