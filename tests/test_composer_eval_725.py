"""The composed answer, measured over the showcase notebook (INBOX 725).

The owner, 2026-10-06: "I want it soooo good it is almost like a chat bot".
The rule that does not move with it: every factual clause is the notes' own
words or a value the app measured (`tests/_composer_eval.py` says how each
measure is taken). These gates hold the composer to the numbers it reached,
so a later change that reads worse, repeats itself or loses a grounded clause
fails here rather than in the owner's hands.
"""

from __future__ import annotations

import pytest

from tests import _composer_eval as ev


@pytest.fixture(scope="module")
def rows():
    return ev.run()


def test_the_eval_covers_25_questions_and_every_shape(rows):
    assert len(rows) == 25
    shapes = {row["shape"] for row in rows}
    assert {"what", "when", "who", "count", "list", "compare", "explain", "status", "yesno", "recent"} <= shapes


def test_every_clause_is_grounded(rows):
    """The rule, over every answer: 1.0, never less."""
    for row in rows:
        assert row["failures"] == [], (row["question"], row["failures"])
        assert row["grounded"] == 1.0


def test_the_same_notebook_and_question_give_the_same_answer(rows):
    again = ev.run()
    assert [row["text"] for row in again] == [row["text"] for row in rows]


def test_the_first_line_answers_the_question_on_every_question(rows):
    """Baseline (INBOX 688's layout): 1 of 25; the opening was a lead-in
    ending in a colon ("Your note **Dentist** says:") and the answer below."""
    missed = [row["question"] for row in rows if not row["first_line"]]
    assert missed == []


def test_nothing_is_said_twice(rows):
    """No two quotes of one answer share as much as a near duplicate does."""
    from tessellate.ai import composer_select

    assert max(row["redundancy"] for row in rows) < composer_select.NEAR_DUPLICATE


def test_answers_read_as_sentences_joined_by_varied_words(rows):
    """Baseline: 3.2 joining phrases an answer, 27 different across the 25;
    sentences of about seven words. INBOX 741 took the per-note "Your note
    ... says:" and "also says:" out (3.6 an answer, 44 different, before it;
    2.56 and 34 after): fewer joins, each one varied and never repeated in an
    answer, so the gate is on variety, not on how many."""
    summary = ev.summary(rows)
    assert summary["connectives_distinct"] >= 30
    assert summary["lead_in_repeats"] == 0
    assert summary["openers_distinct"] >= 10
    assert summary["says_colon"] == 0
    assert 6 <= summary["mean_sentence_words"] <= 14
