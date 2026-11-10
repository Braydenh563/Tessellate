"""A yes/no ask about an event in a window ("is the plumber coming this week") is answered Yes or Not (R9-7):
the event's own date from the answer, against the window the question names. Never guessed: with no date in
the answer's first line, or no window in the question, the answer is left as it is."""

from __future__ import annotations

from datetime import date, timedelta

from tessellate.ai import composer_ahead, recognise



_NAMED = frozenset(composer_ahead._WEEKDAYS) | {m.title() for m in composer_ahead._MONTHS}  # noqa: SLF001


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
    said = recognise.event_window_asked(question)
    day = composer_ahead.date_in(text.split("\n", 1)[0], today) if said else None
    if day is None:
        return text
    first, last = _window(said, today)
    text = composer_ahead.long_form(text, today)
    if first <= day <= last:
        #: A weekday or a month starts the sentence with its capital ("Yes, Tuesday 10 November at 2pm").
        return f"Yes, {text if text.split(None, 1)[0].strip(',.') in _NAMED else text[:1].lower() + text[1:]}"
    return f"No, not {said}. {text}"


def apply(question: str, reply: dict | None, today: date) -> dict | None:
    """The digest reply with its text led by the verdict."""
    if not reply or not reply.get("text"):
        return reply
    text = verdict(question, reply["text"], today)
    return reply if text == reply["text"] else {**reply, "text": text, "parts": [("template", text)]}
