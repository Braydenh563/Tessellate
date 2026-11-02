"""A conversion asked as a question is answered on the device (INBOX 1550).

The owner asked "what is 7000 km in miles??" in Agent mode with Web on: the
utility recogniser knew "7000 km in miles" but not with "what is" in front, so
the question went to the web, failed, and was labelled "From your notes". The
class is every lead a person puts before a conversion or a currency sum."""

from __future__ import annotations

import pytest

from tessellate.ai import utilities

LEADS = ["", "what is ", "what's ", "whats ", "how much is ", "convert ", "can you tell me what is ", "please what is "]


@pytest.mark.parametrize("lead", LEADS)
@pytest.mark.parametrize(("ask", "kind"), [("7000 km in miles", "units"), ("12 stone in kg", "units"),
                                           ("30 c to f", "units"), ("50 usd in eur", "currency")])
def test_a_lead_before_a_conversion_keeps_it_a_conversion(lead, ask, kind):
    for end in ("", "?", "??"):
        assert utilities.kind_of(f"{lead}{ask}{end}") == kind, f"{lead}{ask}{end}"


def test_the_answer_is_worked_out():
    said = " ".join(text for _, text in utilities.answer("what is 7000 km in miles??"))
    assert "4,349" in said or "4349" in said, said
