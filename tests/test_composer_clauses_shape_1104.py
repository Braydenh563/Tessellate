"""composer-subject-1029.md items 3 and 4: a command verb leads any clause, not
only the sentence, and footer words come from the answer shape, not a list."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_ask, composer_unfound


@pytest.mark.parametrize(("text", "kept"), [
    ("after the trip, draft a message to Sara", "after the trip, Sara"),
    ("sourdough; then summarise the starter", "sourdough; starter"),
    ("Lisbon and then draft a message to Sara", "Lisbon and Sara"),
    ("the budget and merge the two lentil soup notes", "the budget and lentil soup notes"),
])
def test_a_command_verb_leading_a_later_clause_is_dropped(text, kept):
    got = composer_ask._without_command(text)
    def flat(t):
        return t.replace(",", "").replace(";", "").replace(" and then", " and").replace(" then", "")

    assert flat(got) == flat(kept), got


@pytest.mark.parametrize(("text", "want"), [
    ("compare my running notes and my baking notes", "running notes and my baking notes"),
    ("books I am reading and add", "books I am reading and add"),
    ("what did I add to the pasta", "what did I add to the pasta"),
    ("my notes and add the pasta", "my notes and pasta"),
    ("what is in my notes; list the groceries", "what is in my notes; list the groceries"),
])
def test_a_verb_inside_a_clause_is_kept(text, want):
    assert composer_ask._without_command(text) == want


@pytest.mark.parametrize("question", [
    "show me what I did in the hotel",
    "list notes with the lentils",
    "tell me about my week in the garden",
    "tell me what I wrote in a hotel",
])
def test_a_place_after_an_order_verb_is_still_a_topic(question):
    stems = composer_unfound._frame_stems(question)
    for word in ("hotel", "lentils", "garden"):
        assert composer_unfound._stem(word) not in stems


@pytest.mark.parametrize(("question", "word"), [
    ("summarise sourdough in a haiku", "haiku"),
    ("give me sourdough as a table", "table"),
    ("explain sourdough in a nutshell", "nutshell"),
    ("show sourdough with a timeline", "timeline"),
    ("give me the top three memos about sourdough", "memos"),
    ("can you write sourdough in two snippets", "snippets"),
])
def test_a_word_the_answer_shape_names_is_a_frame_word(question, word):
    assert composer_unfound._stem(word) in composer_unfound._frame_stems(question)


def test_a_topic_after_in_is_not_a_frame_word():
    assert composer_unfound._stem("lisbon") not in composer_unfound._frame_stems("what did I do in Lisbon")
    assert composer_unfound._stem("hotel") not in composer_unfound._frame_stems("what is in the hotel")
    assert composer_unfound._stem("hotel") not in composer_unfound._frame_stems("what did I do in a hotel")
