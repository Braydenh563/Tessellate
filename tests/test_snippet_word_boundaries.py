"""A quoted line starts and ends at a word, never through one.

Owner, 2026-10-12 (BACKLOG "Source notes"): the source cards began mid-word
("uding servers"). The cause was `engine._snippet`, which cut a 160-character
window out of the flattened body at a character offset, and the card
previews, which cut the end at a character count.
"""

from __future__ import annotations

import pytest

from tessellate.ai import cards
from tessellate.search import engine
from tessellate.search.snippet import clip_words, window_words

BODY = (
    "Notes from the meeting about hosting. We discussed several options including servers "
    "in the cloud, a small office machine, and a managed database for the whole team to share."
)


def test_clip_words_ends_at_a_word_with_an_ellipsis():
    out = clip_words(BODY, 60)
    assert out.endswith("…") and len(out) <= 60
    assert BODY.startswith(out[:-1].rstrip())
    assert out[:-1].split()[-1].strip(",.") in {w.strip(",.") for w in BODY.split()}


def test_clip_words_leaves_a_short_text_alone():
    assert clip_words("a short line", 60) == "a short line"
    assert clip_words("", 60) == ""


def test_clip_words_keeps_one_long_word_whole_rather_than_nothing():
    assert clip_words("x" * 100, 20) == "x" * 19 + "…"


def test_window_starts_after_the_cut_word_and_ends_at_a_word():
    start = BODY.index("servers") - 5  # inside "including"
    out = window_words(BODY, start, 60)
    assert out.startswith("…")
    body = out.strip("…")
    assert body.split()[0] in BODY.split()
    assert body.split()[-1] in BODY.split()
    assert out.endswith("…")


def test_window_at_the_start_has_no_leading_ellipsis():
    out = window_words(BODY, 0, 60)
    assert not out.startswith("…") and out.startswith("Notes from")


def test_window_at_the_end_has_no_trailing_ellipsis():
    out = window_words(BODY, len(BODY) - 30, 160)
    assert out.endswith("share.") and not out.endswith("…")


@pytest.mark.parametrize("term", ["servers", "database", "meeting"])
def test_engine_snippet_is_whole_words_around_the_match(term):
    text = ("lorem ipsum dolor sit amet " * 12) + BODY + (" and then some more filler words" * 6)
    out = engine._snippet(text, [term])
    words = {w.strip(",.;:-") for w in text.split()}
    inner = [w.strip(",.;:-") for w in out.strip("…").split()]
    assert term in out.lower()
    assert inner[0] in words and inner[-1] in words


def test_card_snippet_ends_at_a_word():
    item = cards._note_item({"id": 3, "content": " ".join([BODY] * 3)})
    snippet = item["snippet"]
    assert snippet.endswith("…")
    assert snippet[:-1].split()[-1].strip(",.") in {w.strip(",.") for w in BODY.split()}
