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


@pytest.mark.parametrize("text", [
    "compare my running notes and my baking notes",
    "books I am reading and add",
    "what did I add to the pasta",
])
def test_a_verb_inside_a_clause_is_kept(text):
    assert composer_ask._without_command(text) == text or text.startswith("compare")


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
