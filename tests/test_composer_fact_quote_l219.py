"""L219: a fact asked for (who, how much) is the sentence that holds it, not padding.

Measured before on an 18-sentence note (share of the note's characters the answer
quotes): "who leads the pricing page review" 30%, "how much is the budget" 19%.
After: 12% and 13%, one sentence each.
"""

from __future__ import annotations

import pytest

from tests.test_composer_yearly_244 import ask

BODY = (
    "# Harbor launch plan\n\nHarbor is the mobile app for the team. "
    + " ".join(f"Background detail number {i} about the design review and the vendors." for i in range(4))
    + " The launch date is 14 December. The beta closes on 20 November. Priya leads the pricing page review."
    " Sam owns the app store submission. The budget is $12,000 for the whole project. "
    + " ".join(f"Closing remark {i} about retrospectives." for i in range(3))
)
NOTES = [{"id": 1, "created_at": "2026-10-20", "content": BODY}]


@pytest.mark.parametrize("question,fact,other", [
    ("who leads the pricing page review", "Priya leads the pricing page review.", "budget"),
    ("how much is the budget", "The budget is $12,000", "Priya"),
])
def test_a_fact_ask_quotes_the_one_sentence(question, fact, other):
    text = ask(question, NOTES)
    assert fact in text and other not in text and "Background detail" not in text, text
    assert len(text) / len(BODY) <= 0.15, len(text) / len(BODY)


def test_a_summary_ask_still_quotes_several_sentences():
    text = ask("what is Harbor", NOTES)
    assert text.count(".") >= 3, text
