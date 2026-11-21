"""L-chat-191 (the owner: "when I press ask this question again ... the composer doesnt change it up"):
three regenerations of each of the 25 eval questions, asked as the route asks (turn n + 1, retry n).

Measured 2026-11-14 on `tests/fixtures/composer/showcase_725.json`: 21 of 25 questions give three different
texts (20 before `retry` moved every wording pick), none gives one text, and the closest two answers of a
question are 0.09 apart by words on average. The four that repeat have two-variant lead-ins."""

from __future__ import annotations

from tests import _composer_eval


def test_ask_again_changes_the_words_and_keeps_the_notes():
    spread = _composer_eval.regeneration_spread()
    assert spread["questions"] == 25
    assert spread["all_different"] >= 21, spread
    assert spread["closest_pair_mean"] >= 0.085, spread


def test_no_question_gives_the_same_text_three_times():
    data = _composer_eval.load()
    for entry in data["questions"]:
        texts = {a["text"] for a in _composer_eval.regenerations(entry["question"])}
        assert len(texts) >= 2, entry["question"]


def test_every_regeneration_stays_grounded():
    data = _composer_eval.load()
    on = _composer_eval.today(data)
    for entry in data["questions"][:12]:
        notes = _composer_eval.notes_for(entry, data)
        for result in _composer_eval.regenerations(entry["question"]):
            assert not _composer_eval.trace_failures(result, entry["question"], notes, on), entry["question"]


def test_the_maxims_lint_is_zero_over_every_regeneration_too():
    """L-chat-197: the lint of `tests/test_validate.py` holds over the 75 Ask again answers (25 questions, three each),
    not only the first answer of each."""
    from tessellate.ai import validate

    data = _composer_eval.load()
    notes = data["notes"]
    found = [
        (entry["question"], f.as_dict())
        for entry in data["questions"]
        for result in _composer_eval.regenerations(entry["question"])
        for f in validate.maxims(result, entry["question"], notes) + validate.computed_rule(result, entry["question"])
    ]
    assert found == []
