"""A conversion asked as a question is answered on the device (INBOX 1550).

The owner asked "what is 7000 km in miles??" in Agent mode with Web on: the
utility recogniser knew "7000 km in miles" but not with "what is" in front, so
the question went to the web, failed, and was labelled "From your notes". The
class is every lead a person puts before a conversion or a currency sum."""

from __future__ import annotations

from datetime import datetime

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


#: The rest of the class: a sum, a percentage and a count of days, behind the same leads.
#: "convert" leads a conversion only.
@pytest.mark.parametrize("lead", [lead for lead in LEADS if lead != "convert "])
@pytest.mark.parametrize(("ask", "kind"), [("12 * 7", "sum"), ("17 plus 26", "sum"), ("20% of 50", "percent"),
                                           ("15 percent of 80", "percent")])
def test_a_lead_before_a_sum_keeps_it_a_sum(lead, ask, kind):
    for end in ("", "?", "??"):
        assert utilities.kind_of(f"{lead}{ask}{end}") == kind, f"{lead}{ask}{end}"


NOW = datetime(2026, 11, 2, 10)


@pytest.mark.parametrize(
    ("ask", "said"),
    [
        ("how many days between 1 March 2026 and 2 April 2026", "is 32 days"),
        ("days from 1 March 2026 to 2 April 2026", "is 32 days"),
        ("how many weeks between 1 March 2026 and 30 April 2026", "is 8 weeks and 4 days"),
        ("how much is 20% of 50", "20% of 50 is 10"),
    ],
)
def test_the_days_between_two_dates_are_counted_on_the_device(ask, said):
    answer = utilities.answer(ask, now=NOW)
    assert answer and said in " ".join(text for _, text in answer), answer


def test_a_day_the_device_cannot_read_is_not_counted():
    assert utilities.answer("how many days between monday and the dentist", now=NOW) is None
