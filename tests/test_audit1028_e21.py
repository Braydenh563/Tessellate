"""Audit 1028 E21: a month in a computed answer has its capital."""

from __future__ import annotations

import re

import pytest

from tests.test_composer_route_688 import _ask

_MONTHS = "january february march april may june july august september october november december".split()


def _said(client, question):
    return _ask(client, question, use_tools=False)["text"]


def _unquoted(text: str) -> str:
    """The answer without the note's own quoted words (they are the person's)."""
    return re.sub(r"“[^”]*”", "", text)


# --- E21: a month in a computed answer has its capital ------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "what is 3 weeks after 12 november",
        "how long since 1 january",
        "how many days between 12 november and 3 december",
        "how many weeks until 25 december",
        "what is 10 days before 3 march",
        "how many days until 12 november",
    ],
)
def test_a_computed_date_answer_has_no_lowercase_month(client, question):
    said = _unquoted(_said(client, question))
    assert not re.search(rf"\b\d{{1,2}} (?:{'|'.join(_MONTHS)})\b", said), said


