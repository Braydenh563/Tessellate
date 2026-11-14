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


def test_a_summary_ask_with_no_dominant_sentence_still_quotes_several():
    """L-chat-247 moved this: with one sentence 1.5 times the rest the summary is short;
    a note whose sentences all say Harbor equally is still quoted at length."""
    flat = "# Harbor\n\nHarbor ships on web. Harbor ships on iOS. Harbor ships on Android. Harbor syncs offline."
    text = ask("what is Harbor", [{"id": 1, "created_at": "2026-10-20", "content": flat}])
    assert text.count(".") >= 3, text


@pytest.mark.parametrize("question", ["what is Harbor", "tell me about Harbor"])
def test_a_summary_ask_quotes_at_most_two_sentences_and_a_fifth_of_the_note(question):
    """L-chat-247: one sentence scores 1.5 times the others, so the filler is not quoted.

    Measured before: "what is Harbor" quoted 28% of the 18-sentence note (3 sentences,
    one of them background filler), "tell me about Harbor" 23%.
    """
    text = ask(question, NOTES)
    body = text.split(" From your")[0]
    assert "Harbor is the mobile app for the team." in body and "Background detail" not in text, text
    assert body.count(". ") + 1 <= 2, text
    assert len(body) / len(BODY) <= 0.20, len(body) / len(BODY)
