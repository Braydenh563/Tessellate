"""Q34, WORLD_CLASS rows 35 and 37: a natural voice that reads on this computer.

The engine is the `piper-tts` wheel (a pip extra) and the voice two pinned files (a download
extra), both optional and never vendored. Every engine here is a fake voice object: real
synthesis is checked once by `test_real_piper_speaks`, which runs only where
`TESSELLATE_PIPER_VOICE` names a voice file and the wheel is installed.
"""

from __future__ import annotations

import io
import os
import re
import wave

import pytest

from tessellate.ai import natural_voice
from tessellate.core import extra_downloads, extras

RATE = 22050


class _Chunk:
    def __init__(self, samples: int) -> None:
        self.audio_int16_bytes = b"\x01\x00" * samples


class _Config:
    sample_rate = RATE


class FakeVoice:
    """Speaks 100 ms per word: deterministic times for the transcript."""

    config = _Config()

    def __init__(self) -> None:
        self.said: list[str] = []

    def synthesize(self, text: str):
        self.said.append(text)
        yield _Chunk(RATE // 10 * len(text.split()))


@pytest.fixture(autouse=True)
def _clean():
    extras.reset_for_tests()
    natural_voice.release()
    yield
    extras.reset_for_tests()
    natural_voice.release()


@pytest.fixture()
def fake(monkeypatch):
    voice = FakeVoice()
    monkeypatch.setattr(natural_voice, "available", lambda: True)
    monkeypatch.setattr(natural_voice, "_load", lambda: voice)
    return voice


# --- the catalogue ---------------------------------------------------------------------


def test_the_engine_is_a_pinned_wheel_and_the_voice_two_pinned_files():
    engine = extras.EXTRAS_BY_ID["naturalvoice"]
    voice = extras.EXTRAS_BY_ID["naturalvoice-voice"]
    assert engine.kind == "pip" and engine.packages == ("piper-tts==1.8.0",) and engine.module == "piper"
    assert engine.licence == "GPL-3.0-or-later"
    assert voice.kind == "download" and voice.licence == "Public domain" and voice.version
    names = []
    for download in voice.downloads:
        assert download.url.startswith("https://huggingface.co/rhasspy/piper-voices/resolve/")
        assert "/main/" not in download.url, "a commit, so the bytes cannot move"
        assert re.fullmatch(r"[0-9a-f]{64}", download.sha256) and download.size > 0 and download.unpack == "file"
        names += [name for _member, name in download.members]
    assert names == [natural_voice.VOICE_FILE, natural_voice.VOICE_CONFIG]


def test_the_bundle_installs_both_and_a_computer_with_no_wheel_is_told_so(client, monkeypatch):
    bundle = next(b for b in extras.BUNDLES if b.id == "naturalvoice")
    assert bundle.extras == ("naturalvoice", "naturalvoice-voice")
    monkeypatch.setattr(extra_downloads, "platform_key", lambda: "linux-x86_64")
    assert not any(extras.unavailable_reason(extras.EXTRAS_BY_ID[i]) for i in bundle.extras)
    monkeypatch.setattr(extra_downloads, "platform_key", lambda: "windows-arm64")
    rows = {row["id"]: row for row in client.get("/extras").json()["extras"]}
    for extra_id in bundle.extras:
        assert "No Piper build for this computer" in rows[extra_id]["unavailable"]


def test_listing_the_packages_reaches_no_network(client, monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("the network was touched without an install click")

    monkeypatch.setattr(extra_downloads, "_open_url", refuse)
    assert client.get("/extras").status_code == 200
    assert client.get("/voice/status").json()["speak"]["available"] is False


# --- the text ---------------------------------------------------------------------------


def test_text_is_spoken_without_markdown_or_link_addresses():
    assert natural_voice.plain("**Bold** and [a link](https://x.test/p) and `code`, [[Note]]") == "Bold and a link and code, Note"


def test_sentences_split_at_full_stops_and_keep_abbreviation_free_text_whole():
    assert natural_voice.sentences("One thing. Two things! Is it three? Yes.") == [
        "One thing.",
        "Two things!",
        "Is it three?",
        "Yes.",
    ]
    assert natural_voice.sentences("version 3.5 is out") == ["version 3.5 is out"]


def test_a_very_long_sentence_is_cut_at_a_clause_not_mid_word():
    long = ", ".join(["a clause that goes on and on"] * 40)
    parts = natural_voice.sentences(long)
    assert len(parts) > 1 and all(len(p) <= natural_voice.MAX_SENTENCE for p in parts)
    assert " ".join(parts).replace(", ", " ").split() == long.replace(", ", " ").split()


# --- rendering --------------------------------------------------------------------------


def test_render_times_each_sentence_from_the_audio_it_made(fake):
    wav, segments = natural_voice.render(["One two three.", "Four five."])
    assert [s["text"] for s in segments] == ["One two three.", "Four five."]
    assert segments[0] == {"start": 0, "end": 300, "text": "One two three."}
    assert segments[1]["start"] == 300 + natural_voice.PAUSE_MS and segments[1]["end"] == segments[1]["start"] + 200
    with wave.open(io.BytesIO(wav)) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, RATE)
        ms = audio.getnframes() * 1000 // RATE
    assert abs(ms - (segments[1]["end"] + natural_voice.PAUSE_MS)) <= 1


def test_render_reports_progress_and_stops_between_sentences(fake):
    seen = []
    natural_voice.render(["A b.", "C d."], progress=lambda done, total: seen.append((done, total)))
    assert seen == [(1, 2), (2, 2)]
    calls = iter([False, True])
    with pytest.raises(natural_voice.Stopped):
        natural_voice.render(["A b.", "C d."], should_stop=lambda: next(calls))
    assert fake.said[-1] == "A b.", "the second sentence was never spoken"


# --- the route --------------------------------------------------------------------------


def test_speak_without_the_package_says_where_to_get_it(client):
    response = client.post("/voice/speak", json={"text": "Hello there."})
    assert response.status_code == 503 and "Settings, Packages" in response.json()["detail"]


def test_speak_answers_a_wav_and_keeps_nothing(client, fake, tmp_path):
    response = client.post("/voice/speak", json={"text": "Hello there. This is a note."})
    assert response.status_code == 200 and response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "no-store"
    assert response.content[:4] == b"RIFF" and fake.said == ["Hello there.", "This is a note."]


def test_speak_with_nothing_to_say_is_a_plain_400(client, fake):
    response = client.post("/voice/speak", json={"text": " ** "})
    assert response.status_code == 400 and "nothing to read" in response.json()["detail"]


def test_speak_reads_only_the_first_twelve_thousand_characters(client, fake):
    client.post("/voice/speak", json={"text": ("Word " * 4000).strip() + "."})
    assert sum(len(s) + 1 for s in fake.said) <= natural_voice.MAX_CHARS + 2


def test_status_names_the_missing_half(client):
    body = client.get("/voice/status").json()["speak"]
    assert body["available"] is False and "Settings, Packages" in body["hint"]


# --- the real engine --------------------------------------------------------------------


@pytest.mark.skipif(
    not (os.environ.get("TESSELLATE_PIPER_VOICE") and natural_voice.engine_installed()),
    reason="needs the piper-tts wheel and TESSELLATE_PIPER_VOICE=<en_US-ljspeech-medium.onnx>",
)
def test_real_piper_speaks():
    wav, segments = natural_voice.render(["This is a short test of the offline studio."])
    with wave.open(io.BytesIO(wav)) as audio:
        seconds = audio.getnframes() / audio.getframerate()
    assert 1.5 < seconds < 8 and segments[0]["end"] > 1000
