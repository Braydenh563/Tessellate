"""One Audio section (WORLD_CLASS_PLAN 28.5 row 3): a meeting, a voice memo
and dictation are separate entries (the owner: "meeting notes should be
different ... from dictation"), each a palette row whose `about` is the catalogue's line, so each
is also a Quick access tile through `quickCatalogue`. Live captions is
Brief 82's palette act; the translator joins only when /voice/status lists
it."""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
#: The boot scripts plus the lazy ones the rows live in.
def _js() -> str:
    """Built per use, not held from collection on: the app's code plus a file is 27 MB a copy."""
    return app_js_text() + "".join(
        (ROOT / "frontend/js" / name).read_text(encoding="utf-8")
        for name in ("dashboard.js", "app-features.js", "settings-panes.js", "reveal-targets.js", "meetings.js")
    )


def test_each_audio_entry_is_a_palette_row_with_an_about():
    for label, reveal in (
        ("ph:users-three New meeting", "meeting-new"),
        ("ph:microphone Record a meeting or lecture", "meeting"),
        ("ph:microphone-stage Voice note", "voice-note"),
        ("ph:microphone Dictate a note", "notes-dictation"),
    ):
        assert f'"{label}"' in _js()
        assert f'reveal: "{reveal}"' in _js()
    #: The line under Voice note, Dictate a note and Recordings is the feature
    #: catalogue's own for the same `reveal` (`paletteAbouts`), written once.
    group = _js().split('{ group: "Audio", items: [')[1].split("] },")[0]
    for reveal in ("voice-note", "notes-dictation", "recordings"):
        assert re.search(rf'desc: "[^"]+", reveal: "{reveal}"', group)


def test_the_features_browser_has_an_audio_group():
    group = _js().split('{ group: "Audio", items: [')[1].split("] },")[0]
    for reveal in ("meeting-new", "meeting", "voice-note", "notes-dictation"):
        assert f'reveal: "{reveal}"' in group


def test_a_voice_note_is_the_recorder_named_for_what_it_makes():
    #: openVoiceNote lives in the lazy meetings bundle, so the target loads it first.
    assert '"voice-note": { open: () => ensureModule("meetings").then(() => openVoiceNote())' in _js()
    assert 'classList.add("voice-note")' in _js()
    assert "saveVoiceNoteText" in _js()


def test_live_captions_is_in_the_audio_group_and_translate_waits(client):
    group = _js().split('{ group: "Audio", items: [')[1].split("] },")[0]
    assert "toggleLiveCaptions()" in group
    body = client.get("/voice/status").json()
    assert body["translate"] is False
