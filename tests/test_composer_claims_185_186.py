"""L-chat-185 and L-chat-186 (the owner, 2026-10-10): the composer says what a picture shows only from the
caption the app stored, labelled as the app's reading; and it never reports the asking word as missing from
the notes ("These notes do not mention “summarise”")."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer

PICTURE = "Leafeon\n\n![s.png](/media/s1.png)"
CAPTION = "\n\n[Pictures in this note, as this app read them:\n- s.png: shows A green fox]"
ASKS = ["what is in my Leafeon note", "what does the picture in the Leafeon note show", "describe the image in Leafeon"]


def _say(question: str, body: str) -> str:
    notes = [{"id": 1, "created_at": "2026-10-20T10:00:00", "tags": ["x"], "content": body}]
    return composer.compose(question, notes, today=date(2026, 11, 2))["text"]


@pytest.mark.parametrize("question", ASKS)
def test_a_picture_with_no_stored_caption_is_never_described(question):
    text = _say(question, PICTURE).lower()
    assert "shows" not in text and "fox" not in text, text


@pytest.mark.parametrize("question", ASKS)
def test_a_stored_caption_is_said_as_the_pictures_reading_in_that_note(question):
    assert _say(question, PICTURE + CAPTION) == "The picture in **Leafeon** shows a green fox."


JOKES = [{"id": 1, "created_at": "2026-10-20T10:00:00", "tags": ["joke"], "content": "Jokes\n\nWhy did the chicken cross the road? To get to the other side."}]


@pytest.mark.parametrize("verb", ["summarise", "summarize", "summary of", "give me a summary of", "tldr", "gist of"])
@pytest.mark.parametrize("notes", [[], JOKES], ids=["no notes", "unrelated notes"])
def test_the_asking_verb_is_never_reported_as_missing_from_the_notes(verb, notes):
    text = composer.compose(f"{verb} the harbour", notes, today=date(2026, 11, 2))["text"]
    quoted = {part.strip("“” ").lower() for part in text.replace("“", "|").replace("”", "|").split("|")[1::2]}
    assert not quoted & {"summarise", "summarize", "summary", "tldr", "gist"}, text
