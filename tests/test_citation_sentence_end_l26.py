"""L26 (E51): a citation mark follows the whole sentence it vouches for, never a clause cut off
by a comma ("... is $200[1], a gap of about $30 between them."). The one deliberate exception
is a "when" answer's mark after its day (`anchor`, tests/test_gold_answers.py)."""

from __future__ import annotations

import pytest

from tests.test_gold_answers import FIXTURE, _answer


def _rows(item):
    result = _answer(item)
    return result["text"], [g for g in result.get("grounding") or [] if not g.get("anchor")]


@pytest.mark.parametrize("item", FIXTURE["answers"], ids=lambda a: str(a["n"]))
def test_no_mark_lands_before_a_trailing_clause(item):
    text, rows = _rows(item)
    for row in rows:
        sentence = row.get("sentence") or ""
        at = text.find(sentence)
        if at < 0:
            continue
        after = text[at + len(sentence):at + len(sentence) + 2]
        assert not after.startswith((", ", "; ")), (sentence[-40:], text[at:at + len(sentence) + 40])


def test_the_clause_after_a_comma_is_part_of_the_grounded_sentence():
    item = next(a for a in FIXTURE["answers"] if a["n"] == 2)
    text, rows = _rows(item)
    assert any(r["sentence"].endswith("a gap of about $30 between them") for r in rows), [r["sentence"][-50:] for r in rows]


def test_the_when_answer_keeps_its_mark_after_the_day():
    item = next(a for a in FIXTURE["answers"] if a["n"] == 21)
    row = _answer(item)["grounding"][0]
    assert row["anchor"] == "On 17 July"
