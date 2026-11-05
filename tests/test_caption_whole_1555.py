"""A picture's caption is said whole (INBOX 1555).

The owner: "the composer's mention of the caption cut off". The caption "A
photo of a grassy hill with blue arrows pointing to different features and a
caption that says ..." was said as "a grassy hill with blue arrows pointing
to different.": `caption_said` read "features", a noun here, as the
caption's verb and kept only what came before it. The picture line said "shows
A photo of ...", its frame unread; and the picture's link in the answer named
the note by its words run together ("random ahh sketch random ahh sketch").
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from tessellate.ai import composer
from tessellate.ai.composer_threads import caption_said
from tests._app_js import app_js_text

HILL = 'A photo of a grassy hill with blue arrows pointing to different features and a caption that says "CRAZZYYYY 67".'


@pytest.mark.parametrize(
    ("caption", "said"),
    [
        (HILL, 'a grassy hill with blue arrows pointing to different features and a caption that says "CRAZZYYYY 67"'),
        ("An image of a desk with several monitors and a lamp that shows the time", "a desk with several monitors and a lamp that shows the time"),
        ("A picture of a long table covered in plants and books that contains a cat", "a long table covered in plants and books that contains a cat"),
        #: The frames it was built for still read past the verb.
        ("A photo depicts a black gaming mouse", "a black gaming mouse"),
        ("a picture of a gaming mouse depicts its buttons", "a gaming mouse"),
        ("a pencil sketch of a dragon", "a pencil sketch of a dragon"),
    ],
)
def test_a_noun_that_is_also_a_verb_does_not_cut_the_caption(caption, said):
    assert caption_said(caption) == said


def _note(i: int, title: str, caption: str) -> dict:
    return {
        "id": i, "created_at": "2026-10-20T10:00:00", "tags": ["sketches"],
        "content": f"{title}\n\n![s.png](/media/s{i}.png)\n\n[Pictures in this note, as this app read them:\n- s.png: shows {caption}]",
    }


@pytest.mark.parametrize("question", ["notes about sketches", "what is in my random ahh sketch note", "tell me about my sketches"])
def test_the_answer_says_the_caption_past_its_frame_and_whole(question):
    notes = [_note(1, "random ahh sketch", HILL), _note(4, "Gary The Moss Monster :D", "A drawing of a green moss monster with big eyes.")]
    text = composer.compose(question, notes, today=date(2026, 11, 2))["text"]
    assert "pointing to different features and a caption" in text
    assert "A photo of" not in text


def test_a_picture_link_names_its_note_by_its_name():
    js = app_js_text()
    assert "`From note ${n}: ${noteNamePlain(entry.content, 40)}`" in js
    assert re.search(r"const title = g\.title \|\| noteNamePlain\(content, 60\);", js)
