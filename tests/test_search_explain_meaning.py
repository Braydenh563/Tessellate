"""Row 13, dog3-1026: a plain keyword hit was labelled "similar meaning" because
any vector pair has a cosine above zero. The label now needs a close vector."""

from __future__ import annotations

from tessellate.search import engine

ROW = {"title": "", "body": "estates general met in may", "tags": ""}


def _say(bm25: float, cosine: float) -> list[str]:
    return engine._explain({"bm25": bm25, "cosine": cosine, "graph": 0.0}, ROW, ["estates"], None)


def test_a_word_match_with_a_faint_vector_is_only_a_word_match():
    assert _say(1.0, 0.30) == ["matched your words"]


def test_a_word_match_with_a_close_vector_says_both():
    assert _say(1.0, 0.80) == ["matched your words", "similar meaning"]


def test_a_note_only_meaning_found_says_meaning():
    assert _say(0.0, 0.40) == ["similar meaning"]
