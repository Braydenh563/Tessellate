"""A yes/no ask about an event in a window ("is the plumber coming this week") is answered Yes or Not (R9-7):
the event's own date from the answer, against the window the question names. Never guessed: with no date in
the answer's first line, or no window in the question, the answer is left as it is."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from tessellate.ai import composer_ahead, recognise



_NAMED = frozenset(calendar.day_name) | {m.title() for m in composer_ahead._MONTHS}  # noqa: SLF001


def _month_end(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _window(phrase: str, today: date) -> tuple[date, date]:
    """The first and last day the phrase names."""
    monday = today - timedelta(days=today.weekday())
    saturday = monday + timedelta(days=5)
    next_month = _month_end(today) + timedelta(days=1)
    if phrase.split()[-1].lower() in recognise._WINDOW_DAYS:  # noqa: SLF001
        #: "on Thursday" is the next Thursday on or after today: an event asked about is still to come.
        found = recognise.span(phrase.split()[-1], today, "future")
        return (found[0], found[1]) if found else (today, today)
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


#: Words that make "are we meeting on Tuesday" a question about the day, not about a named thing.
_GENERIC = frozenset("are we am i will do have is there be an a the any meeting meetings meet meeting call calls sync catch up catch-up".split())
_MEETING = re.compile(r"\b(?:meeting|meetings|sync|call|catch-?up|stand-?up|1:1|interview)\b", re.I)


def day_question(question: str) -> str:
    """"are we meeting on Tuesday" asks of the day, so it is read as "what is on Tuesday"; "" when the question
    names a thing (a person, a place) or has no window."""
    said = recognise.event_window_asked(question)
    if not said or not recognise.EVENT_LEAD or not _MEETING.search(question):
        return ""
    core = re.findall(r"[a-z0-9:'-]+", recognise.without_event_window_tail(question).lower())
    if any(word not in _GENERIC for word in core):
        return ""
    return f"what is {said}" if said.startswith("on ") else f"what is on {said}"


def answer(question: str, run, today: date) -> dict | None:  # noqa: ANN001
    """`run(question)` led by its verdict. A meeting ask with no named thing is declined here: the plan lists the
    day and leads it with a verdict (`lead`)."""
    return None if day_question(question) else apply(question, run(question), today)


def lead(question: str, text: str) -> str:
    """"Yes." when the day's list holds a meeting, else "No meeting is written for <window>."."""
    if _MEETING.search(text):
        return "Yes."
    return f"No meeting is written for {recognise.event_window_asked(question).removeprefix('on ')}."
