"""An overview of many notes is a summary, not every note inline
(composer-1031, item 3; INBOX 1461: "one list sentence of six names";
"six notes", five cited, "Two notes more on the right" and "Show four
more" disagree).

The shape, measured on the owner's ten university notes (no model):
the count once; one line naming two or three notes, then "and N more";
at most five lines before the fold; the Show more label counts the folded
lines; every note counted is cited or said to be on the right.

Fixed clock: Friday 30 October 2026, 10:00 (the 1461 fixture).
"""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer_digest, realise
from tests.test_composer_route_688 import _ask
from tests.test_composer_timing_1461 import MORE, NOTES, ask  # noqa: F401

QUESTIONS = ["What have I saved about courses & study?", "tell me about uni", "tell me about courses & study",
             "what have I got on courses & study", "what have I written about uni"]


@pytest.fixture
def answer(ask, monkeypatch):  # noqa: F811
    """The whole event set for a question, through the 1461 fixture."""
    import tests.test_composer_timing_1461 as timing

    got: dict = {}

    def spy(*a, **k):  # noqa: ANN002, ANN003, ANN202
        got.update(_ask(*a, **k))
        return got

    monkeypatch.setattr(timing, "_ask", spy)

    def run(notes, question: str) -> tuple[str, dict, set]:  # noqa: ANN001
        text = ask(notes, question)
        support = next((g["support"] for g in got.get("grounding", []) if g.get("support")), {})
        cited = {s["note_id"] for g in got.get("grounding", []) for s in g.get("sentences", [])}
        return text, support, cited

    return run


def _paragraphs(text: str) -> list[str]:
    return [p for p in text.split("\n\n") if p.strip()]


@pytest.mark.parametrize("question", QUESTIONS)
def test_ten_notes_are_summarised_by_name_then_counted(answer, question):
    text, _support, _cited = answer(NOTES + MORE, question)
    paras = _paragraphs(text)
    assert re.match(r"(?:You have|Your notebook holds|Found) ten notes\b", paras[0]), paras[0]
    named = re.match(r"They include (.+) and (\w+) more\.$", paras[1])
    assert named, paras[1]
    shown = len(re.split(r", | and ", named.group(1)))
    assert 2 <= shown <= 3, paras[1]
    assert named.group(2) == realise.count_word(10 - shown), paras[1]
    assert "the Cloud computing" not in text and "the had " not in text, text


@pytest.mark.parametrize("question", QUESTIONS)
def test_the_fold_and_the_counts_agree(answer, question):
    text, support, cited = answer(NOTES + MORE, question)
    paras = _paragraphs(text)
    more = (support.get("more") or {}).get("lines") or []
    if more:
        first_folded = paras.index(more[0])
        #: The opening, the summary line, then at most LINES told lines.
        assert first_folded - 2 <= composer_digest.LINES["overview"], paras[:first_folded]
        assert support["more"]["label"] == f"Show {realise.count_word(len(more))} more"
    right = re.search(r"\b(\w+) more on the right\.", text)
    on_right = 0 if not right else {realise.count_word(n).lower(): n for n in range(1, 11)}[right.group(1).lower()]
    assert len(cited) + on_right == 10, (sorted(cited), right)
    #: The total is said once.
    assert len(re.findall(r"\bten notes\b", text)) == 1, text


@pytest.mark.parametrize("question", QUESTIONS[:3])
def test_a_few_notes_are_told_not_summarised(answer, question):
    text, _support, _cited = answer(NOTES, question)
    assert "They include" not in text, text
