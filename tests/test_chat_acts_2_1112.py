"""Closing the acts agent's leftovers (L-chat-25 to L-chat-31): the composer's overview subject,
the stray which-do-you-mean, one time format on an act card. Fixed clock: Thursday 12 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt

from tessellate.ai import composer
from tests.test_composer_688 import _note

NOW = dt.datetime(2026, 11, 12, 10, 0)
TODAY = NOW.date()
SOURDOUGH = [
    _note(1, "# Sourdough log\n\nFed the sourdough starter at 8. Rye flour works well.", 1, tags=["sourdough"]),
    _note(2, "# More sourdough\n\nA long cold proof gives sourdough an open crumb.", 2, tags=["sourdough"]),
    _note(3, "# Bread tin sizes\n\nA sourdough loaf needs a 900g tin.", 3, tags=["sourdough"]),
]


def _say(question: str) -> str:
    return composer.compose(question, SOURDOUGH, today=TODAY, now=NOW)["text"]


def test_an_overview_ask_does_not_become_its_own_subject():
    """L-chat-30: 'give me an overview of my sourdough notes' is about sourdough."""
    text = _say("give me an overview of my sourdough notes").lower()
    assert "give me" not in text and "overview of my" not in text
    assert "sourdough" in text


def test_summarise_my_notes_asks_no_which_do_you_mean():
    """L-chat-31: a subject asked whole is answered, not disambiguated."""
    text = _say("summarise my sourdough notes")
    assert "which do you mean" not in text.lower()


def test_a_morning_and_an_afternoon_reminder_read_alike():
    """L-chat-25: "at 9" beside "at 3pm" read as two formats; every clock says its half of the day."""
    from datetime import datetime

    from tessellate.ai.commands import _clock

    assert _clock(datetime(2026, 11, 13, 9, 0)) == "9am"
    assert _clock(datetime(2026, 11, 13, 15, 0)) == "3pm"
    assert _clock(datetime(2026, 11, 13, 9, 30)) == "9:30am"
