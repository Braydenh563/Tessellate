"""L252 (audit G10): "between 8 and 10" is a window that starts at 8, so the reminder is due then, not at the 9:00 default."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import reminder_parser

NOW = datetime(2026, 11, 14, 12, 0)


@pytest.mark.parametrize(
    ("said", "hour", "words"),
    [
        ("plumber thursday between 8 and 10", 8, "Plumber"),
        ("call Ana between 8pm and 10pm", 20, "Call Ana"),
        ("call Ana from 8 to 10pm", 20, "Call Ana"),
        ("take the bins out tonight between 8 and 9", 20, "Take the bins out"),
        ("meet Sam from 11am to 1pm", 11, "Meet Sam"),
    ],
)
def test_a_clock_window_is_due_when_it_opens(said, hour, words):
    got = reminder_parser.read_by_rule(said, NOW)
    assert got is not None
    assert got["due_at"].hour == hour and got["due_at"].minute == 0, got
    assert got["text"] == words
    assert "clock_unsaid" not in got


def test_a_date_range_is_not_a_clock_window():
    got = reminder_parser.read_by_rule("hotel between 1 and 5 October", NOW)
    assert got is None or got["due_at"].hour == 9
