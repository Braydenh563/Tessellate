"""Q34, WORLD_CLASS row 35: the overview is a job that ends as a saved recording.

The voice is a fake (100 ms per word); real synthesis is checked in `test_natural_voice_q34.py`.
"""

from __future__ import annotations

import io
import json
import time
import wave

import pytest

from tessellate.ai import natural_voice
from tessellate.api import routes_studio
from tessellate.core import deps, extras, recording_make
from tessellate.core.database import Entry
from tests.test_natural_voice_q34 import RATE, FakeVoice


@pytest.fixture(autouse=True)
def _clean():
    extras.reset_for_tests()
    natural_voice.release()
    routes_studio._runs.clear()
    yield
    natural_voice.release()
    routes_studio._runs.clear()


@pytest.fixture()
def voice(monkeypatch):
    fake = FakeVoice()
    monkeypatch.setattr(natural_voice, "available", lambda: True)
    monkeypatch.setattr(natural_voice, "_load", lambda: fake)
    return fake


def _note(client, text, **extra):
    response = client.post("/entries", json={"content": text, **extra})
    assert response.status_code in (200, 201), response.text
    return response.json()


def _wait(client, run_id):
    for _ in range(200):
        run = client.get(f"/studio/runs/{run_id}").json()
        if run["state"] != "running":
            return run
        time.sleep(0.05)
    raise AssertionError("the run never ended")


def test_without_the_natural_voice_it_says_where_to_get_it(client):
    response = client.post("/studio/overview", json={})
    assert response.status_code == 503 and "Settings, Packages" in response.json()["detail"]


def test_an_empty_notebook_has_nothing_to_read(client, voice):
    response = client.post("/studio/overview", json={})
    assert response.status_code == 422 and "nothing" in response.json()["detail"]


def test_an_overview_becomes_a_recording_with_timed_lines(client, voice):
    _note(client, "Garden plan\nPlant the beans in May. Water twice a week.")
    _note(client, "Call the plumber\nThe tap in the kitchen drips.")
    started = client.post("/studio/overview", json={"minutes": 3})
    assert started.status_code == 202
    body = started.json()
    assert body["title"] == "Overview of recent notes" and body["script"][0].startswith("Here is an overview")
    run = _wait(client, body["id"])
    assert run["state"] == "done" and run["recording_id"]
    item = client.get(f"/recordings/{run['recording_id']}").json()
    assert item["derived"] == "overview" and item["state"] == "saved" and item["transcribed"] is True
    assert item["mime"] == "audio/wav" and item["duration_ms"] > 1000 and item["peaks"]
    lines = client.get(f"/recordings/{run['recording_id']}/transcript").json()
    texts = [seg["text"] for seg in lines["segments"]]
    assert texts == body["script"], "the transcript is exactly what was spoken"
    audio = client.get(f"/media/recordings/{run['recording_id']}")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"
    assert voice.said == body["script"]


def test_a_topic_reads_only_the_notes_that_hold_it(client, voice):
    _note(client, "Garden plan\nPlant the beans in May.")
    _note(client, "Tax return\nSend the form before April.")
    body = client.post("/studio/overview", json={"topic": "garden"}).json()
    _wait(client, body["id"])
    assert body["title"] == "Overview of garden"
    assert any("Garden plan" in line for line in body["script"])
    assert not any("Tax" in line for line in body["script"])


def test_a_brief_is_the_same_builder_with_its_own_frame(client, voice):
    _note(client, "Sam\nWants the budget numbers. Prefers short emails.")
    body = client.post("/studio/overview", json={"topic": "Sam", "brief": True}).json()
    run = _wait(client, body["id"])
    assert body["script"][0] == "Here is a brief about Sam, from your own notes."
    assert client.get(f"/recordings/{run['recording_id']}").json()["derived"] == "brief"


def test_a_private_note_is_never_read(client, voice):
    secret = _note(client, "Secret\nThe safe code is 1234.")
    session = deps.get_db().session()
    session.query(Entry).filter(Entry.id == secret["id"]).update({"is_private": True})
    session.commit()
    session.close()
    _note(client, "Public\nThe garden needs water.")
    body = client.post("/studio/overview", json={}).json()
    _wait(client, body["id"])
    assert not any("safe code" in line or "Secret" in line for line in body["script"])


def test_stop_ends_the_run_and_keeps_no_recording(client, voice, monkeypatch):
    _note(client, "One\nFirst thing here. Second thing here.")
    gate = {"stop": False}
    real = natural_voice.render

    def waiting(lines, should_stop=None, progress=None):
        while not gate["stop"]:
            time.sleep(0.01)
        return real(lines, should_stop=should_stop, progress=progress)

    monkeypatch.setattr(natural_voice, "render", waiting)
    body = client.post("/studio/overview", json={}).json()
    assert client.post(f"/studio/runs/{body['id']}/stop").json()["stopped"] is True
    gate["stop"] = True
    run = _wait(client, body["id"])
    assert run["state"] == "stopped" and run["recording_id"] is None
    assert client.get("/recordings").json()["recordings"] == []


def test_an_engine_that_breaks_is_a_run_that_says_so(client, voice, monkeypatch):
    _note(client, "One\nFirst thing here.")

    def broken(*_a, **_k):
        raise RuntimeError("engine fell over: /secret/path")

    monkeypatch.setattr(natural_voice, "render", broken)
    run = _wait(client, client.post("/studio/overview", json={}).json()["id"])
    assert run["state"] == "failed" and "Settings, Packages" in run["error"] and "secret" not in run["error"]


def test_the_waveform_and_length_come_from_the_wav():
    pcm = (b"\x00\x40" * RATE) + (b"\x00\x00" * RATE)
    out = io.BytesIO()
    with wave.open(out, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(pcm)
    peaks = recording_make.peaks_of(out.getvalue())
    assert recording_make.duration_ms(out.getvalue()) == 2000
    assert len(peaks) <= recording_make.PEAK_BARS and peaks[0] == 100 and peaks[-1] == 0
    json.dumps(peaks)
