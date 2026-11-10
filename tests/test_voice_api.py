"""Voice endpoints: graceful without Whisper, working with it."""

from __future__ import annotations

from tessellate.ai import voice


def test_status_reports_unavailable_with_hint(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: False)
    body = client.get("/voice/status").json()
    assert body["available"] is False
    assert "Voice notes" in body["hint"] and "Settings, Packages" in body["hint"]


def test_transcribe_without_whisper_is_503_with_hint(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: False)
    response = client.post(
        "/voice/transcribe", files={"file": ("clip.webm", b"fake-audio", "audio/webm")}
    )
    assert response.status_code == 503
    assert "Voice notes" in response.json()["detail"] and "Settings, Packages" in response.json()["detail"]


def test_transcribe_with_fake_whisper(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(
        voice, "transcribe", lambda path, model_size="base": "buy milk tomorrow"
    )
    response = client.post(
        "/voice/transcribe", files={"file": ("clip.webm", b"fake-audio", "audio/webm")}
    )
    assert response.status_code == 200
    assert response.json() == {"text": "buy milk tomorrow"}
    # It landed in the audit log too.
    audit = client.get("/audit?limit=10").json()
    assert any(row["action"] == "transcribed" for row in audit)


def test_transcribe_rejects_empty_recording(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    response = client.post(
        "/voice/transcribe", files={"file": ("clip.webm", b"", "audio/webm")}
    )
    assert response.status_code == 400


def test_transcribe_model_load_failure_is_503_not_422(client, monkeypatch):
    # Reproduces the reported "meeting transcription errors out": with
    # faster-whisper installed but the model download failing (offline,
    # blocked, corporate proxy), the old code let the exception fall
    # through to the route's catch-all and reported "Couldn't transcribe
    # that recording", indistinguishable from a genuinely bad clip. It
    # should instead say the model couldn't load, as a 503 (retry later),
    # not a 422 (this specific recording is the problem).
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(
        voice,
        "_get_model",
        lambda size: (_ for _ in ()).throw(OSError("no route to huggingface.co")),
    )
    response = client.post(
        "/voice/transcribe", files={"file": ("clip.webm", b"fake-audio", "audio/webm")}
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "model" in detail.lower()
    assert "recording" not in detail.lower()


def test_status_available_with_fake_whisper(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    body = client.get("/voice/status").json()
    assert body["available"] is True
    assert body["hint"] is None
    assert body["model"] == "base"


# --- the dictation model-size preference ---------------------------------------
#
# `voice_model` was read by this route from the moment it shipped, but had no
# field in `PreferencesBody` and nothing in Settings ever wrote it, every
# install silently ran "base" regardless of what a user picked, because there
# was no way to pick anything.


def test_voice_model_preference_roundtrips(client):
    assert client.get("/preferences").json()["voice_model"] == "base"
    updated = client.put("/preferences", json={"voice_model": "small"}).json()
    assert updated["voice_model"] == "small"
    assert client.get("/preferences").json()["voice_model"] == "small"


def test_an_unknown_voice_model_is_rejected(client):
    assert client.put("/preferences", json={"voice_model": "huge"}).status_code == 422


def test_the_chosen_voice_model_reaches_the_transcriber(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    seen = {}

    def fake_transcribe(path, model_size="base"):
        seen["model_size"] = model_size
        return "ok"

    monkeypatch.setattr(voice, "transcribe", fake_transcribe)
    client.put("/preferences", json={"voice_model": "small"})
    client.post(
        "/voice/transcribe", files={"file": ("clip.webm", b"fake-audio", "audio/webm")}
    )
    assert seen["model_size"] == "small"


def test_a_clip_is_decoded_here_when_pyav_refuses_faster_whispers_argument(monkeypatch, tmp_path):
    """The owner's log, 2026-10-11: faster-whisper 1.1 passes `metadata_errors`
    to `av.open`, PyAV 14 refuses it, and every recording failed to transcribe.
    The samples are decoded here and handed over instead."""
    from types import SimpleNamespace

    from tessellate.ai import voice

    class Model:
        def transcribe(self, audio):
            if isinstance(audio, str):
                raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")
            return [SimpleNamespace(start=0.0, end=1.5, text=" hello there ")], None

    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "_get_model", lambda size: Model())
    monkeypatch.setattr(voice, "_decode_samples", lambda path: [0.0] * 16000)
    assert voice.transcribe_segments(tmp_path / "clip.webm") == [{"start": 0, "end": 1500, "text": "hello there"}]


def test_any_other_type_error_from_the_model_is_not_swallowed(monkeypatch, tmp_path):
    import pytest

    from tessellate.ai import voice

    class Model:
        def transcribe(self, audio):
            raise TypeError("something else")

    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "_get_model", lambda size: Model())
    with pytest.raises(TypeError, match="something else"):
        voice.transcribe_segments(tmp_path / "clip.webm")
