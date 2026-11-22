"""A "what time" ask answered by a note that names the day but no time of day (R3-18): the lead says so, so the
reader is not left to wonder whether the time was missed."""

from __future__ import annotations

import re
from datetime import date

from tessellate.ai import composer_ahead

NOTE = "The note gives the day but no time."
_WHAT_TIME = re.compile(r"^\s*(?:at )?what time\b", re.I)
#: "9:30", "8am", "noon", "half past two": a clock time in words or digits.
_CLOCK = re.compile(r"\b\d{1,2}[:.]\d{2}\b|\b\d{1,2} ?(?:am|pm)\b|\b(?:noon|midday|midnight|o'clock|half past|quarter (?:past|to))\b", re.I)


def missing_time(question: str, fact: str) -> bool:
    """Whether `question` asks what time and `fact` has a day but no clock time."""
    if not _WHAT_TIME.match(question or "") or _CLOCK.search(fact or ""):
        return False
    return composer_ahead.date_in(fact, date(2000, 1, 1)) is not None


def say_noted(say_fact, out, lead, today: date, cleaned: str, question: str) -> None:  # noqa: ANN001
    """`say_fact`, then, for a "what time" ask whose note has no clock time, the line saying so."""
    say_fact(out, lead, today, question)
    if out.lines and missing_time(cleaned, lead.sentence.text):
        out.lines[-1] = f"{out.lines[-1]} {NOTE}"
