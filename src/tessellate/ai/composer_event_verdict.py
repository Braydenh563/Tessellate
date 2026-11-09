"""A yes/no ask about an event in a window ("is the plumber coming this week") is answered Yes or Not (R9-7):
the event's own date from the answer, against the window the question names. Never guessed: with no date in
the answer's first line, or no window in the question, the answer is left as it is."""

from __future__ import annotations

import re
from datetime import date, timedelta

from tessellate.ai import composer_ahead

_ASK = re.compile(
    r"^\W*(?:is|are|will)\s+(?:the|my|our|a)\b.*?\s+(?P<window>this week|next week|this weekend|next weekend|this month|next month|today|tomorrow|tonight)\s*[?.!]*$",
    re.IGNORECASE,
)


def _month_end(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _window(phrase: str, today: date) -> tuple[date, date]:
    """The first and last day the phrase names."""
    monday = today - timedelta(days=today.weekday())
    saturday = monday + timedelta(days=5)
    next_month = _month_end(today) + timedelta(days=1)
    return {
        "this week": (monday, monday + timedelta(days=6)),
        "next week": (monday + timedelta(days=7), monday + timedelta(days=13)),
        "this weekend": (saturday, saturday + timedelta(days=1)),
        "next weekend": (saturday + timedelta(days=7), saturday + timedelta(days=8)),
        "this month": (today.replace(day=1), _month_end(today)),
        "next month": (next_month, _month_end(next_month)),
        "today": (today, today),
        "tonight": (today, today),
        "tomorrow": (today + timedelta(days=1), today + timedelta(days=1)),
    }[phrase]


def verdict(question: str, text: str, today: date) -> str:
    """`text` with "Yes, " or "Not <window>: " before it, or as it was."""
    #: A question that long is no event ask; the lazy `.*?` would be quadratic on it (CodeQL).
    found = _ASK.match(" ".join(question.split())) if question and len(question) < 300 else None
    day = composer_ahead.date_in(text.split("\n", 1)[0], today) if found else None
    if day is None:
        return text
    said = found.group("window").lower()
    first, last = _window(said, today)
    if first <= day <= last:
        return f"Yes, {text[:1].lower()}{text[1:]}"
    return f"No, not {said}. {text}"


def apply(question: str, reply: dict | None, today: date) -> dict | None:
    """The digest reply with its text led by the verdict."""
    if not reply or not reply.get("text"):
        return reply
    text = verdict(question, reply["text"], today)
    return reply if text == reply["text"] else {**reply, "text": text, "parts": [("template", text)]}
