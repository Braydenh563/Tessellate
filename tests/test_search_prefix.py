"""Typing part of a word finds it in the universal finder.

The owner, 2026-09-21: "on the universal find anything search, notes, boards,
and documents etc only match on a whole word. so they will only appear if I
write 'test' and not 'tes' but idk if that's intentional or not."

It was not intentional, and the reason recorded for the threshold that caused
it could not happen: the comment said three letters would turn "the" into
"the*", but "the" is a stopword and `query.search_terms` drops it before the
prefix stage ever sees it. These tests hold both halves, so neither the
threshold nor the premise can quietly move back.
"""

import time

from tessellate.search import query as query_understanding
from tessellate.search import search_manager
from tessellate.search.engine import _match_expression


def test_a_three_letter_word_is_tried_as_a_prefix():
    assert _match_expression(["tes"], [], [], "prefix") == "(tes*)"


def test_a_full_word_still_is_too():
    assert _match_expression(["test"], [], [], "prefix") == "(test*)"


def test_two_letters_are_left_whole_on_purpose():
    """The FTS5 table is built with no `prefix=` option, so a prefix query
    walks the term list. Two letters is a cost question that wants the index
    option and a measurement, not a smaller constant."""
    assert _match_expression(["ab"], [], [], "prefix") == "(ab)"


def test_the_threshold_is_shared_not_copied():
    """It was written out as a bare 4 in the finder while the note search kept
    its own constant, which is how the two stages stopped agreeing."""
    engine_source = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "src" / "tessellate" / "search" / "engine.py"
    ).read_text(encoding="utf-8")
    assert "PREFIX_MIN_LEN" in engine_source
    assert "len(term) >= 4" not in engine_source


def test_the_reason_the_threshold_gave_cannot_happen():
    """"the" never reaches the prefix stage, so it could never have been
    starred. If a future change lets stopwords through, this fails and the
    threshold's justification has to be rewritten rather than assumed."""
    assert query_understanding.search_terms("the") == []
    assert search_manager.PREFIX_MIN_LEN == 3


def test_the_whole_word_stage_is_unchanged():
    """Prefixing is the second stage. The first still asks for whole words, so
    an exact match cannot be outranked by a longer word that merely starts the
    same way."""
    assert _match_expression(["tes"], [], [], "all") == "(tes)"


def test_building_a_prefix_expression_is_not_slow():
    """Cheap, but it runs on every keystroke in the finder, so it is measured
    rather than assumed."""
    terms = [f"term{n}" for n in range(20)]
    started = time.process_time()
    for _ in range(1000):
        _match_expression(terms, [], [], "prefix")
    elapsed = time.process_time() - started
    assert elapsed < 1.0, f"1000 expressions took {elapsed:.3f}s"
