"""Findings of the blind answer panel (PR 216, CHAT_PLAN decisions 25, 29, 40).

Three raters scored the 25 showcase answers without knowing their source.
What they marked down, fixed at the cause, each pinned here on the showcase
notebook the eval uses.
"""

from __future__ import annotations

import re

from tests import _composer_eval as ev


def _answer(question: str) -> str:
    data = ev.load()
    entry = next(q for q in data["questions"] if q["question"] == question)
    rows = [r for r in ev.run(data) if r["question"] == question]
    assert entry and rows
    return rows[0]["text"]


def test_a_latest_answer_walks_back_in_time_with_words_that_face_back():
    """"Soon after, on 29 August" came after "12 September": a walk back from the
    newest note may not borrow the forward-in-time joiners."""
    text = _answer("What is the latest on the sync rewrite?")
    dates = re.findall(r"(?:\n\n|^)([A-Z][^,\n]*, )?on (\d{1,2} \w+)", text)
    assert len(dates) >= 3, text
    forward = re.compile(r"\b(Soon after|Next|Following that|Then|After that|Afterwards|Subsequently)\b,? on ")
    assert not forward.search(text.split("\n\n", 1)[1]), text


def test_a_when_answer_keeps_the_sentence_that_is_the_date():
    """"When is the boiler service due?" quoted "The pressure keeps dropping" and
    left out "Due in March.": a short sentence that carries the cue the shape
    asks for is the answer, not a sentence that only names the subject."""
    assert "Due in March" in _answer("When is the boiler service due?")
