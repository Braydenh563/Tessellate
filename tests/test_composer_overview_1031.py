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

from tests.test_composer_route_688 import _ask
import tests.test_composer_timing_1461 as timing

ask = timing.ask  #: the 1461 fixture, used here by name
NOTES, MORE = timing.NOTES, timing.MORE

QUESTIONS = ["What have I saved about courses & study?", "tell me about uni", "tell me about courses & study",
             "what have I got on courses & study", "what have I written about uni"]


@pytest.fixture
def answer(ask, monkeypatch):  # noqa: F811
    """The whole event set for a question, through the 1461 fixture."""
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
def test_ten_notes_are_woven_and_counted_once(answer, question):
    """1743 moved the intent: ten notes were "They include X and seven more"; they are now a lead that counts them and a few paragraphs that tell each one (INBOX 1461 asked for no read-back; 1743 for an overview)."""
    text, _support, _cited = answer(NOTES + MORE, question)
    paras = _paragraphs(text)
    assert re.match(r"(?:You have|Your notebook holds|Found) ten notes\b", paras[0]), paras[0]
    assert "They include" not in text and 3 <= len(paras) <= 6, text
    assert "the Cloud computing" not in text and "the had " not in text, text


@pytest.mark.parametrize("question", QUESTIONS)
def test_the_counts_agree_with_no_fold(answer, question):
    """1743 moved the intent: no "Show N more" and no "N more on the right"; every counted note is told and cited, and the total is said once."""
    text, support, cited = answer(NOTES + MORE, question)
    assert not (support.get("more") or {}).get("lines"), support
    assert not re.search(r"\bmore on the right\b", text), text
    assert len(cited) == 10, sorted(cited)
    assert len(re.findall(r"\bten notes\b", text)) == 1, text


@pytest.mark.parametrize("question", QUESTIONS[:3])
def test_a_few_notes_are_told_not_summarised(answer, question):
    text, _support, _cited = answer(NOTES, question)
    assert "They include" not in text, text
