"""L97: the professional register has its own words for the fragments that had none: how many notes
mention a thing, an echoed sentence, a note that lists, the citation tail and the next-question chips.
The natural voice keeps its one wording (a test pins it)."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer, composer_tables
from tessellate.ai.composer_phrases import PHRASES

KEYS = ("mentions_one", "mention_many", "echo", "echo_end", "lists", "cite_from", "cite_from_note",
        "next_tag_a", "next_tag_b", "next_note_a", "next_note_b", "next_latest_a", "next_when_a")
NOTES = [
    {"id": 1, "content": "# Dentist\n\nDentist appointment on 4 November at 3pm. Floss more.", "created_at": "2026-10-02T09:00:00", "tags": ["health", "admin"]},
    {"id": 2, "content": "Called the dentist about the invoice.", "created_at": "2026-10-09T09:00:00", "tags": ["admin"]},
]


@pytest.mark.parametrize("key", KEYS)
def test_every_fragment_has_professional_wording_and_natural_keeps_its_own(key):
    professional = composer_tables.VOICE_VARIANTS["professional"][key]
    assert professional and (key == "next_tag_b" or all(PHRASES[k] != PHRASES[key] for k in professional))
    assert composer_tables.VOICE_VARIANTS["natural"][key] == (key,)
    for name in professional:
        text = PHRASES[name]
        assert "\u2014" not in text and "!" not in text
        assert text.endswith(" ") == PHRASES[key].endswith(" ") and text.startswith(" ") == PHRASES[key].startswith(" ")


@pytest.mark.parametrize("a, b", [("echo", "echo_end"), ("next_tag_a", "next_tag_b"), ("next_note_a", "next_note_b")])
def test_a_pair_has_equal_lengths_and_the_second_follows_the_first(a, b):
    voices = composer_tables.VOICE_VARIANTS["professional"]
    assert len(voices[a]) == len(voices[b]) and composer_tables.PAIRED[b] == a


def _chips(voice: str, question: str) -> list[str]:
    got = composer.compose(question, NOTES, today=date(2026, 10, 31), voice=voice)
    return got["next"]


def test_the_chips_follow_the_voice():
    natural = _chips("natural", "when is the dentist")
    professional = _chips("professional", "when is the dentist")
    assert natural and professional
    assert natural != professional
    assert all(not c.startswith(("What else do my notes", "When did I write about", "What is the latest on")) for c in professional), professional
    assert all(c.endswith("?") for c in professional)
