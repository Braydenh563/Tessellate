"""Speaker labels behind the model gate (WORLD_CLASS 28.5 row 11, Brief 81).
Turns are cut by timing (a pause over 1.5 s or a new paragraph); the model
names them from what is said. With no model nothing is labelled. Every
model here is the fake transport (CLAUDE.md section 4): how a real small
model names turns is not measured.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tessellate.ai import speakers, voice
from tessellate.core import transcript

HERE = Path(__file__).parent / "fixtures" / "meetings"
SEGMENTS = transcript.clean(json.loads((HERE / "launch_sync.segments.json").read_text()))
WEBM_HEAD = b"\x1a\x45\xdf\xa3" + b"\x00" * 60


class _Manager:
    def utility_model(self) -> str:
        return "fake"


class _Model:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.sent: list[list[dict]] = []

    def chat(self, model: str, messages: list[dict], mode: str | None = None) -> dict:
        self.sent.append(messages)
        return {"content": self.reply}


def test_turns_cut_at_a_pause_over_one_and_a_half_seconds_or_a_paragraph() -> None:
    assert transcript.turns(SEGMENTS) == [[0, 1], [2, 3], [4]]
    para = [*SEGMENTS[:2], {**SEGMENTS[1], "start": 6200, "end": 7000, "paragraph": True}]
    assert transcript.turns(transcript.clean(para)) == [[0, 1], [2]]


def test_the_sample_gets_two_speakers() -> None:
    model = _Model("1 | Sam\n2 | Priya\n3 | Sam")
    out = speakers.label(SEGMENTS, ["Sam", "Priya"], _Manager(), model)
    assert [s["speaker"] for s in out] == ["Sam", "Sam", "Priya", "Priya", "Sam"]
    assert len({s["speaker"] for s in out}) == 2
    prompt = model.sent[0][1]["content"]
    assert prompt.startswith("People at the meeting: Sam, Priya.") and "\n2. Thanks Sam." in prompt
    #: The input is never changed.
    assert all(s["speaker"] is None for s in SEGMENTS)


def test_a_reply_naming_too_few_turns_labels_nothing() -> None:
    out = speakers.label(SEGMENTS, [], _Manager(), _Model("1 | Sam\nI am not sure about the rest"))
    assert all(s["speaker"] is None for s in out)


def test_parse_names_keeps_only_real_turns_and_short_names() -> None:
    names = speakers.parse_names("1 | Sam\n2: Speaker A\n9 | Priya\n3 | the person who spoke about money\n- 3. Alex", 3)
    assert names == {1: "Sam", 2: "Speaker A", 3: "Alex"}


def _recording(client) -> int:
    rid = client.post("/recordings", json={"title": "Launch sync", "mime": "audio/webm"}).json()["id"]
    client.post(f"/recordings/{rid}/chunk", files={"file": ("c.webm", WEBM_HEAD, "audio/webm")}, data={"duration_ms": "4000"})
    client.post(f"/recordings/{rid}/finish", json={"duration_ms": 3_663_000})
    return rid


def test_with_a_model_the_transcript_carries_speakers(app_state, fake_ollama, monkeypatch) -> None:
    from tessellate.api.app import create_app

    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "transcribe_segments", lambda path, model_size="base": SEGMENTS)
    fake_ollama.librarian_reply = "1 | Sam\n2 | Priya\n3 | Sam"
    client = TestClient(create_app())
    rid = _recording(client)
    body = client.post(f"/recordings/{rid}/transcribe").json()
    assert [s["speaker"] for s in body["segments"]] == ["Sam", "Sam", "Priya", "Priya", "Sam"]
    assert client.get(f"/recordings/{rid}/transcript").json()["speakers"] is True
    vtt = client.get(f"/recordings/{rid}/transcript.vtt").text
    assert "\n<v Priya>Thanks Sam." in vtt
    #: Named again on demand, for a transcript made while the model was off.
    fake_ollama.librarian_reply = "1 | Ana\n2 | Ben\n3 | Ana"
    again = client.post(f"/recordings/{rid}/speakers").json()
    assert again["speakers"] is True and again["segments"][2]["speaker"] == "Ben"


def test_with_no_model_nothing_is_labelled(client, monkeypatch) -> None:
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "transcribe_segments", lambda path, model_size="base": SEGMENTS)
    rid = _recording(client)
    body = client.post(f"/recordings/{rid}/transcribe").json()
    assert all(s["speaker"] is None for s in body["segments"])
    response = client.post(f"/recordings/{rid}/speakers")
    assert response.status_code == 503 and "local AI" in response.json()["detail"]


def test_a_speaker_is_renamed_everywhere_without_a_model(app_state, fake_ollama, monkeypatch) -> None:
    """Ledger 1514: PUT /recordings/{id}/speakers changes one label on every turn it names."""
    from tessellate.api.app import create_app

    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "transcribe_segments", lambda path, model_size="base": SEGMENTS)
    fake_ollama.librarian_reply = "1 | Sam\n2 | Priya\n3 | Sam"
    client = TestClient(create_app())
    rid = _recording(client)
    client.post(f"/recordings/{rid}/transcribe")
    renamed = client.put(f"/recordings/{rid}/speakers", json={"from_name": "Sam", "to_name": "Samir"})
    assert renamed.status_code == 200
    assert [s["speaker"] for s in renamed.json()["segments"]] == ["Samir", "Samir", "Priya", "Priya", "Samir"]
    missing = client.put(f"/recordings/{rid}/speakers", json={"from_name": "Nobody", "to_name": "X"})
    assert missing.status_code == 404
