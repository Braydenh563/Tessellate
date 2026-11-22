"""A caption that is a whole sentence is not spliced after "shows" (INBOX 1599).

The owner: "The picture in your Leafeon Pokemon image test note shows a
vibrant, lush forest scene depicts several light-colored Eevee creatures
gathered by a stream." A captioner's sentence has its own verb; a noun phrase
may follow "shows" (its leading article lowered), a sentence stands in quotes.
Every path that says a picture (the quote path and the digest path) and every
caption shape goes through the one rule `composer_threads.caption_form`.
"""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer
from tessellate.ai.composer_threads import caption_form

FOREST = "A vibrant, lush forest scene depicts several light-colored Eevee creatures gathered by a stream."


@pytest.mark.parametrize(
    ("caption", "whole", "said"),
    [
        ("A green fox", False, "a green fox"),
        ("A green fox.", False, "a green fox"),
        ("Leafeon at sunset", False, "Leafeon at sunset"),
        ("An old wooden desk with a lamp that shows the time", False, "an old wooden desk with a lamp that shows the time"),
        ("A photo depicts a black gaming mouse", False, "a black gaming mouse"),
        (FOREST, True, FOREST.rstrip(".")),
        (FOREST.rstrip("."), True, FOREST.rstrip(".")),
        ("A forest scene. Several Eevee gather by a stream. Light fills the trees.", True, "A forest scene. Several Eevee gather by a stream. Light fills the trees"),
        ("Leafeon sits in a vibrant forest", True, "Leafeon sits in a vibrant forest"),
        ("The Eevee is resting by a stream", True, "The Eevee is resting by a stream"),
    ],
)
def test_caption_form_tells_a_sentence_from_a_noun_phrase(caption, whole, said):
    assert caption_form(caption) == (whole, said)


def _note(caption: str) -> list[dict]:
    return [{
        "id": 1, "created_at": "2026-10-20T10:00:00", "tags": ["x"],
        "content": f"Leafeon Pokemon image test\n\n![s.png](/media/s1.png)\n\n[Pictures in this note, as this app read them:\n- s.png: shows {caption}]",
    }]


def _ask(question: str, caption: str) -> str:
    return composer.compose(question, _note(caption), today=date(2026, 11, 2))["text"]


QUESTIONS = ["what is in my Leafeon Pokemon image test note", "tell me about my Leafeon Pokemon image test note", "notes about x"]


@pytest.mark.parametrize("question", QUESTIONS)
@pytest.mark.parametrize("caption", [FOREST, FOREST.rstrip("."), "A forest scene. Several Eevee gather by a stream.", "Leafeon sits in a vibrant forest."])
def test_a_sentence_caption_is_never_spliced_after_shows(question, caption):
    text = _ask(question, caption)
    assert " shows A " not in text and " shows a vibrant" not in text and "shows Leafeon" not in text
    assert "shows a forest scene" not in text
    assert "“" in text and caption.rstrip(".").split(".")[0] in text


@pytest.mark.parametrize("question", QUESTIONS)
@pytest.mark.parametrize("caption", ["A green fox", "A green fox.", "An old desk with a lamp"])
def test_a_noun_phrase_caption_follows_shows_lowercased(question, caption):
    text = _ask(question, caption)
    assert " shows a" in text and " shows A" not in text and " shows An" not in text


def test_a_name_caption_keeps_its_capital():
    assert " shows Leafeon at sunset" in _ask(QUESTIONS[0], "Leafeon at sunset")


def test_the_owners_girl_with_bell_caption_is_said_once_as_a_picture():
    """CHAT_PLAN, the owner's 2026-10-10 bugs (L-chat-19): "The picture in Girl with bell shows The image shows
    a snowy scene..." said the captioner's frame inside the app's own."""
    from tessellate.ai.composer_threads import caption_form

    whole, said = caption_form(
        'The image shows a snowy scene with a girl holding a bell, and there is a signature at the bottom left that reads "24-12-2018"'
    )
    assert not whole and said.startswith("a snowy scene with a girl holding a bell"), said
    assert "image shows" not in said.lower()
