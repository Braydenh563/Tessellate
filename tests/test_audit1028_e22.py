"""Audit 1028 E22: instruction words are never reported as missing evidence."""

from __future__ import annotations

import re

import pytest

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def _said(client, question):
    return _ask(client, question, use_tools=False)["text"]


# --- E22: instruction words are never reported as missing evidence --------------------


@pytest.fixture
def money(session):
    manager.create_entry(session, "# Budget\n\nRent is 650 a month and groceries are about 120 a week.\n\nSaved 400 towards the trip.", category_name="Personal")
    manager.create_entry(session, "# Gym log\n\nSquats 3 sets of 5 at 80kg. Felt strong on the bench.", category_name="Health")
    session.commit()


@pytest.mark.parametrize(
    ("question", "word"),
    [
        ("what numbers did I write about rent", "numbers"),
        ("give me my rent figures", "figures"),
        ("what is the overall rent figure", "figure"),
        ("simply tell me what I spend on rent", "simply"),
        ("mark what I spent on groceries", "mark"),
        ("what tag fits my budget", "fits"),
        ("show me the amounts for rent", "amounts"),
        ("just list the values for rent", "values"),
        ("basically what do I pay for rent", "basically"),
        ("archive what I wrote about groceries", "archive"),
        ("what total did I save for the trip", "total"),
    ],
)
def test_a_word_that_instructs_is_not_named_as_missing(client, money, question, word):
    said = _said(client, question)
    assert not re.search(rf"[“\"]{word}[”\"]", said, re.I), said


def test_a_real_absent_subject_is_still_named(client, money):
    assert "volcano" in _said(client, "what did I write about my rent and the volcano").lower()


