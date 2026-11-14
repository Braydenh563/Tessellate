"""A saved transcript keeps its times (L578).

The recorder joined the segments into one run of words before the person
saved the note, so the moments were gone from the text. The transcript route
now also answers the segments as `[m:ss] Speaker: text` lines and the
recorder puts those in its review box.
"""

from __future__ import annotations

from tessellate.ai import voice
from tessellate.core import transcript
from tests._app_js import frontend_text


def test_lines_carry_the_time_and_the_speaker():
    segments = [
        {"start": 0, "end": 900, "text": "Hello.", "speaker": None},
        {"start": 65_000, "end": 70_000, "text": "Yes.", "speaker": "Sam"},
        {"start": 3_661_250, "end": 3_662_000, "text": "Late.", "speaker": None},
    ]
    assert transcript.to_lines(segments) == "[0:00] Hello.\n[1:05] Sam: Yes.\n[1:01:01] Late."


def test_no_segments_no_lines():
    assert transcript.to_lines([]) == ""


def test_the_route_answers_lines_too(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    segs = [{"start": 2400, "end": 3000, "text": "Okay.", "speaker": None}]
    monkeypatch.setattr(voice, "transcribe_segments", lambda path, model_size="base": segs)
    head = b"\x1a\x45\xdf\xa3" + b"\x00" * 60
    rid = client.post("/recordings", json={"title": "t", "mime": "audio/webm"}).json()["id"]
    client.post(f"/recordings/{rid}/chunk", files={"file": ("c.webm", head, "audio/webm")}, data={"duration_ms": "4000"})
    client.post(f"/recordings/{rid}/finish", json={"duration_ms": 4000})
    client.post(f"/recordings/{rid}/transcribe")
    assert client.get(f"/recordings/{rid}/transcript").json()["lines"] == "[0:02] Okay."


def test_the_recorder_reviews_the_timed_lines():
    assert "body.lines" in frontend_text("meetings.js")
