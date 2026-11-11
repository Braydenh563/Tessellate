"""Whisper's options from Settings (Brief 87 step 2; ANALYSIS.md "Vendor
candidates, 2026-10-11", rows 1 and 10).

Silence skipping (`vad_filter`, Silero VAD inside faster-whisper, no new
download), a language, and the words to expect (`initial_prompt`) reach
`model.transcribe` from three preferences, through every path that
transcribes: dictation, a recording, a recording in the background.
Measured on 20 synthetic clips, see HISTORY "Brief 87 step 2".
"""

from __future__ import annotations

from tests._help_text import help_more_text
from pathlib import Path

from tessellate.ai import voice
from tessellate.core import deps
from tests._app_js import app_js_text


class _Segment:
    def __init__(self, text: str) -> None:
        self.start, self.end, self.text = 0.0, 1.0, text


class _Model:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def transcribe(self, audio, **kwargs):  # noqa: ANN001
        self.calls.append(kwargs)
        return [_Segment("hello")], None


def test_silence_is_skipped_by_default_and_nothing_else_is_guessed(app_state):
    assert voice.options_from(deps.get_config()) == {"vad_filter": True}


def test_the_three_settings_become_whisper_options(app_state):
    config = deps.get_config()
    config.set_preference("voice_language", "en")
    config.set_preference("voice_vocabulary", "  Margaret, Edinburgh, sourdough  ")
    assert voice.options_from(config) == {
        "vad_filter": True,
        "language": "en",
        "initial_prompt": "Margaret, Edinburgh, sourdough",
    }
    config.set_preference("voice_skip_silence", False)
    assert "vad_filter" not in voice.options_from(config)


def test_an_unknown_language_is_detection_and_a_long_list_is_cut(app_state):
    config = deps.get_config()
    config.set_preference("voice_language", "klingon")
    config.set_preference("voice_vocabulary", "word, " * 200)
    options = voice.options_from(config)
    assert "language" not in options
    assert len(options["initial_prompt"]) <= voice.VOCABULARY_MAX


def test_the_options_reach_the_model(app_state, monkeypatch, tmp_path):
    model = _Model()
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "_get_model", lambda size: model)
    deps.get_config().set_preference("voice_language", "fr")
    assert voice.transcribe(tmp_path / "clip.webm") == "hello"
    assert model.calls == [{"vad_filter": True, "language": "fr"}]


def test_options_passed_in_win_over_the_settings(app_state, monkeypatch, tmp_path):
    model = _Model()
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "_get_model", lambda size: model)
    list(voice.iter_segments(tmp_path / "clip.webm", options={}))
    assert model.calls == [{}]


def test_no_app_state_means_the_plain_call(monkeypatch):
    """A script or test with no app running gets faster-whisper's defaults,
    and no data folder is made to find that out."""
    monkeypatch.setattr(deps, "_config", None)
    made = []
    monkeypatch.setattr(deps, "init_app_state", lambda *a, **k: made.append(1))
    assert voice._options() == {}
    assert made == []


def test_the_preferences_round_trip(client):
    body = client.get("/preferences").json()
    assert body["voice_skip_silence"] is True
    assert body["voice_language"] == ""
    assert body["voice_vocabulary"] == ""
    saved = client.put(
        "/preferences",
        json={"voice_skip_silence": False, "voice_language": "de", "voice_vocabulary": "Bahnhof"},
    )
    assert saved.status_code == 200
    body = client.get("/preferences").json()
    assert (body["voice_skip_silence"], body["voice_language"], body["voice_vocabulary"]) == (False, "de", "Bahnhof")
    assert client.put("/preferences", json={"voice_language": "xx"}).status_code == 422


def test_settings_has_the_three_controls_and_help_names_them():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    for control in ('id="voice-skip-silence"', 'id="voice-language-select"', 'id="voice-vocabulary"'):
        assert control in html
    js = app_js_text() + Path("frontend/js/settings-packages.js").read_text(encoding="utf-8")
    for key in ("voice_skip_silence", "voice_language", "voice_vocabulary"):
        assert key in js

    import re

    text = re.sub(r'"\s*\n\s*"', "", help_more_text())
    assert "Skip silence before transcribing" in text
    assert "Words to expect" in text
