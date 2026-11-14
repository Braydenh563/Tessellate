"""L-chat-244: a yearly-cost ask works the year out from a stated monthly price.

Measured before (composer.compose over the eval notebook's pricing note):
'how much is Plus a year' answered with the monthly sentence and 'None of
these notes say anything about "year"'; $72 appeared in no answer.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.ai import composer, composer_extra, composer_study

PRICING = {"id": 1, "created_at": "2026-10-20", "content": "# Harbor pricing notes\n\nTwo tiers: Free and Plus at $6 a month. Priya wants an annual plan at $60. Decision due by 20 November."}
OTHER = {"id": 2, "created_at": "2026-10-21", "content": "# Gym\n\nThe gym is $30 a month and I go twice a week."}
NOTES = [OTHER, PRICING]


def ask(question: str, notes=NOTES) -> str:
    """The route's pre-note reader (`composer_extra`), then the composer, as `/chat/stream` runs them."""
    reply = composer_extra.answer(composer_study.Ctx(question=question, notes=notes, now=datetime(2026, 11, 14, 10), seed="s", asked=question))
    if reply:
        return reply.text
    return composer.compose(question, [dict(n, connected=False) for n in notes], today=date(2026, 11, 14), now=datetime(2026, 11, 14, 10))["text"]


@pytest.mark.parametrize("question", [
    "how much is Plus a year",
    "How much is Plus per year?",
    "what does Plus cost annually",
    "what's the yearly cost of Plus",
    "how much would Plus cost for a year",
])
def test_the_year_is_twelve_times_the_monthly_price(question):
    text = ask(question)
    assert "$72" in text, text
    assert "Plus is $6 a month" in text and "[**Harbor pricing notes**](#/notes/1)" in text, text
    assert "$30" not in text and "nothing about" not in text.lower(), text


def test_a_price_the_note_already_gives_for_the_year_is_named_beside_it():
    assert "$60" in ask("how much is Plus a year")


def test_the_subject_picks_the_note_not_the_first_monthly_price():
    text = ask("how much is the gym a year")
    assert "$360" in text and "[**Gym**](#/notes/2)" in text and "$72" not in text, text


def test_no_monthly_price_means_no_invented_year():
    text = ask("how much is Plus a year", [{"id": 3, "created_at": "2026-10-20", "content": "# Plus\n\nPlus is the paid tier."}])
    assert "72" not in text, text
