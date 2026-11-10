"""G10 of the second composer audit: "call mum on sunday about christmas plans" keeps
"christmas". A holiday after "about" or "for" is the thing the reminder is about when
another span already gives the time; alone ("buy gifts for christmas") it is still the
time. Read the same by the chat's own act (`commands`) and by Magic Add's rule reader."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands, reminder_parser

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.mark.parametrize(
    "said, words, day",
    [
        ("call mum on sunday about christmas plans", "Call mum about christmas plans", (11, 15)),
        ("pack for christmas on 20 december", "Pack for christmas", (12, 20)),
        ("buy gifts for christmas", "Buy gifts", (12, 25)),
        ("call gran on christmas day", "Call gran", (12, 25)),
    ],
)
def test_the_rule_reader_keeps_a_holiday_that_is_the_subject(said, words, day):
    got = reminder_parser.read_by_rule(said, NOW)
    assert got is not None and got["text"] == words, got
    assert (got["due_at"].month, got["due_at"].day) == day


def test_the_chat_act_reads_it_the_same_way():
    got = commands._reminder("remind me to call mum on sunday about christmas plans", NOW)  # noqa: SLF001
    assert got is not None and got["text"] == "Call mum about christmas plans", got
    assert (got["due_at"].month, got["due_at"].day) == (11, 15)
