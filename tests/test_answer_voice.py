"""The voice of an answer with no model (CHAT_PLAN decision 72, B6).

The owner, 2026-10-11: the voice is picked in Settings. Warm and concise
(the default), Neutral, Playful and Plain; one phrase table each, so the
facts and the shape never change between voices, and a conversation does
not open the same way five turns running.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tessellate.ai import composer_digest
from tests.test_gold_answers import NOTES, TODAY

ROOT = Path(__file__).resolve().parent.parent
QUESTION = "What have I saved about courses & study?"


def test_settings_offers_the_four_voices_with_a_sample():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    select = html[html.index('<select id="pref-voice"'):html.index("</select>", html.index('<select id="pref-voice"'))]
    assert re.findall(r'value="(\w+)"', select) == ["natural", "professional", "playful", "plain"]
    assert "Warm and concise (default)" in select and 'id="pref-voice-sample"' in html


def test_the_settings_sample_is_the_engines_own():
    js = (ROOT / "frontend/js/settings-controls.js").read_text(encoding="utf-8")
    for voice in composer_digest.VOICES:
        assert f"  {voice}: {json.dumps(composer_digest.sample(voice))}," in js, voice


@pytest.mark.parametrize("voice", list(composer_digest.VOICES))
def test_a_voice_changes_the_words_never_the_facts_or_the_shape(voice):
    base = composer_digest.answer(QUESTION, NOTES, today=TODAY)
    said = composer_digest.answer(QUESTION, NOTES, today=TODAY, voice=voice)
    assert [r["sentence"] for r in said["grounding"]] == [r["sentence"] for r in base["grounding"]]
    assert len(said["text"].split("\n\n")) == len(base["text"].split("\n\n"))
    assert said["offer"]["text"] == base["offer"]["text"]


@pytest.mark.parametrize("voice", ["natural", "professional", "playful"])
def test_five_turns_never_open_the_same_way(voice):
    openings = [composer_digest.answer(QUESTION, NOTES, today=TODAY, voice=voice, turn=t)["text"].split("\n\n")[0] for t in range(5)]
    assert len(set(openings)) == 5, openings
    #: No span in the count opener when the question is not about time
    #: (INBOX 1441, the owner, 2026-10-29: "I dont like how it refers to dates").
    assert all("four notes" in o.lower() and "17 July" not in o for o in openings), openings


def test_the_setting_is_saved(client):
    for voice in composer_digest.VOICES:
        saved = client.put("/preferences", json={"composer_voice": voice})
        assert saved.status_code == 200
        read = client.get("/preferences").json()
        assert read["composer_voice"] == voice
