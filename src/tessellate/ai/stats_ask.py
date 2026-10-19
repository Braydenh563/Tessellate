"""Ask about your statistics (INBOX 1319): questions the Statistics page's box
answers from the counts, in plain sentences, with no model.

`notebook_stats.answer` already answers what the chat can be asked about the
notebook as a whole (tags, categories, orphans, totals). This adds what the
page knows and the chat does not: a count in a named month, what you use most
(the usage ledger), whether this month or week is busier than the last, and a
summary of the month or week. Every figure is a count of rows, so the sentence
is complete without a model, and a model that phrases it later has the same
numbers to start from. Anything it cannot count falls to `notebook_stats.answer`,
then to a line saying what it can.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import notebook_stats as ns
from tessellate.ai import questions, recognise
from tessellate.ai.notebook_stats import StatAnswer
from tessellate.core.database import Entry, utcnow


_HOW_MANY = r"how many|number of|\bcount\b|how much"
_USAGE = re.compile(r"\b(?:use|used|using|open|opened)\b.*\bmost\b|\bmost (?:used|use|opened|visited)\b|favou?rite (?:feature|tab)|which features|what features")
_COMPARE = re.compile(
    r"more than|less than|fewer than|compared?\b|versus|\bvs\b|better than|worse than|am i writing|writing more|writing less|up or down|slowing|speeding"
)
_SUMMARY = re.compile(r"summar|overview|recap|sum up|how(?:'s| is| was| has) my (?:month|week)|how am i doing|how(?:'s| is) it going")

#: The ends of the notebook's timeline: "my first note", "oldest", "when did I
#: start", and "my newest note", "when did I last write". A stray word between
#: ("first note ion this notebook") changes nothing, only these anchors count.
_FIRST = re.compile(
    r"\b(?:first|oldest|earliest)\b.*\b(?:notes?|entry|entries)\b|\bwhen did i (?:first )?(?:start|begin)\b"
)
_LATEST = re.compile(
    r"\b(?:newest|latest|last|most recent)\s+(?:\w+\s+)?(?:notes?|entry)\b|\bwhen did i last (?:write|make|add|save|take)\b"
)

HELP_LINE = (
    "I can count your notes, words, tags, reminders and what you use, and say when you wrote your first or newest note. "
    'Try "summarise my month", "what do I use most", "when did I write my first note" or "am I writing more than last month".'
)


def _end_note(session: Session, now: datetime, newest: bool) -> StatAnswer:
    """The first or newest visible note, by date and title: one row, ordered
    by the same column the counts above use."""
    order = (Entry.created_at.desc(), Entry.id.desc()) if newest else (Entry.created_at.asc(), Entry.id.asc())
    row = session.execute(ns._visible(select(Entry.created_at, Entry.content)).order_by(*order).limit(1)).first()
    kind = "latest-note" if newest else "first-note"
    if row is None:
        return StatAnswer(kind, "You have no notes yet.")
    made = row[0] if row[0].tzinfo else row[0].replace(tzinfo=utcnow().tzinfo)
    made = made.astimezone(now.tzinfo)
    title = questions._title(row[1]) or "Untitled"
    which = "newest" if newest else "first"
    return StatAnswer(kind, f"Your {which} note is from {made.day} {made.strftime('%B %Y')}: {title}")


def _span(session: Session, start: datetime, end: datetime) -> dict:
    """Notes, words and reminders done in `[start, end)`, with the notes' tags."""
    counts = ns._week_counts(session, start, end)
    a, b = start.astimezone(utcnow().tzinfo), end.astimezone(utcnow().tzinfo)
    tags: Counter[str] = Counter()
    for (raw,) in session.execute(ns._visible(select(Entry.tags)).where(Entry.created_at >= a, Entry.created_at < b)):
        tags.update(ns._tags_of(raw))
    return {**counts, "tags": tags}


def _midnight(day: date, zone) -> datetime:
    return datetime.combine(day, time(0), zone)


def _month_start(now: datetime, back: int = 0) -> datetime:
    year, month = now.year, now.month - back
    while month < 1:
        year, month = year - 1, month + 12
    return _midnight(date(year, month, 1), now.tzinfo)


def _next_month(start: datetime) -> datetime:
    return _month_start(start, -1)


def _name(start: datetime) -> str:
    return start.strftime("%B")


def _named_month(text: str, now: datetime) -> datetime | None:
    """The first of the month the question names ("in July", "last month",
    "in sept 2025"), read by the recogniser like every other date; a month
    with no year is the latest one that has begun."""
    for start, end, _ in recognise.find(text):
        found = recognise.span(text[start:end], now.date(), "past")
        if found and found[2] == "month":
            return _midnight(found[0], now.tzinfo)
    return None


def _month_count(text: str, session: Session, now: datetime) -> StatAnswer | None:
    if not re.search(_HOW_MANY, text) or ns._SUBJECT_AFTER.search(text):
        return None
    start = _named_month(text, now)
    if start is None:
        return None
    end = min(_next_month(start), now + timedelta(seconds=1))
    n = _span(session, start, end)["notes"]
    words = f"in {start.strftime('%B %Y')}"
    return StatAnswer("month-count", f"You made {ns._plural(n, 'note')} {words}.", [{"label": words, "count": n}])


def _feature(name: str) -> str:
    kind, _, rest = name.partition(":")
    if kind == "tab":
        return f"the {rest.capitalize()} tab"
    return rest.replace("-", " ") or name


def _usage(usage_summary: dict) -> StatAnswer:
    features = [f for f in (usage_summary.get("features") or []) if f.get("count")][:5]
    if not features:
        return StatAnswer("usage", "Nothing is counted yet. Uses are counted on this computer as you move around the app.")
    first, *rest = features
    text = f"You use {_feature(first['name'])} most, {ns._plural(int(first['count']), 'use')}."
    if rest:
        text += " Then " + ", ".join(f"{_feature(f['name'])} ({int(f['count'])})" for f in rest) + "."
    return StatAnswer("usage", text + " Counted on this computer only.", [{"label": _feature(f["name"]), "count": int(f["count"])} for f in features])


def _period(text: str) -> str:
    return "week" if re.search(r"\bweek\b", text) else "month"


def _compare(text: str, session: Session, now: datetime, first_day: int) -> StatAnswer:
    if _period(text) == "week":
        review = ns.week_review(session, now, first_day)
        here, before = review["this"], review["last"]
        label_now, label_before = "this week", "last week"
        verdict_text = (
            f"This week so far you have made {ns._plural(here['notes'], 'note')} and written {ns._plural(here['words'], 'word')}, "
            f"against {ns._plural(before['notes'], 'note')} and {ns._plural(before['words'], 'word')} in all of last week."
        )
    else:
        this_start, last_start = _month_start(now), _month_start(now, 1)
        #: Through the same day of the month, whole days: a note made at noon on
        #: the 19th of last month is on the 19th, whatever time it is now.
        stretch = min(last_start + timedelta(days=now.day), this_start)
        here = _span(session, this_start, now + timedelta(seconds=1))
        before = _span(session, last_start, stretch)
        whole = _span(session, last_start, this_start)
        label_now, label_before = "this month", f"the same date in {_name(last_start)}"
        verdict_text = (
            f"This month so far you have made {ns._plural(here['notes'], 'note')}, against {before['notes']} by the same date in "
            f"{_name(last_start)} ({whole['notes']} in all of {_name(last_start)}). Words written: {here['words']:,} against {before['words']:,}."
        )
    diff = here["notes"] - before["notes"]
    if diff:
        verdict_text += f" That is {abs(diff)} {'more' if diff > 0 else 'fewer'} {'note' if abs(diff) == 1 else 'notes'}."
    lead = "Yes. " if diff > 0 else "About the same. " if diff == 0 else "Not so far. "
    return StatAnswer(
        "compare",
        f"{lead}{verdict_text}",
        [{"label": label_now, "count": here["notes"]}, {"label": label_before, "count": before["notes"]}],
    )


def _summary(text: str, session: Session, now: datetime, first_day: int) -> StatAnswer:
    if _period(text) == "week":
        start, label = ns.week_start(now, first_day), "This week so far"
        previous = ns.week_start(now, first_day) - timedelta(days=7)
    else:
        start, label = _month_start(now), "This month so far"
        previous = _month_start(now, 1)
    here = _span(session, start, now + timedelta(seconds=1))
    pieces = [
        ns._plural(here["notes"], "note"),
        ns._plural(here["words"], "word"),
        f"{ns._plural(here['reminders_done'], 'reminder')} done",
    ]
    text_out = f"{label}: {', '.join(pieces)}."
    if here["tags"]:
        tag, n = here["tags"].most_common(1)[0]
        text_out += f" Most used tag: {tag} ({ns._plural(n, 'note')})."
    #: Whole days, as `_compare`: the same point is the same day, not the same hour.
    before = _span(session, previous, min(previous + timedelta(days=(now.date() - start.date()).days + 1), start))
    gap = here["notes"] - before["notes"]
    same = "week" if _period(text) == "week" else "month"
    if gap:
        text_out += f" That is {abs(gap)} {'more' if gap > 0 else 'fewer'} than by the same point last {same}."
    return StatAnswer(
        "summary",
        text_out,
        [
            {"label": "notes", "count": here["notes"]},
            {"label": "words", "count": here["words"]},
            {"label": "reminders done", "count": here["reminders_done"]},
        ],
    )


def ask(question: str, session: Session, now: datetime, usage_summary: dict, first_day: int = 0) -> StatAnswer:
    """The answer to one question about the page's figures; never raises for
    a question it cannot count, it says what it can."""
    raw = (question or "").strip().lower()
    text = ns._despell(raw)
    if _USAGE.search(text):
        return _usage(usage_summary)
    #: The raw words too: the spelling pass turns "start" into "stats".
    if _FIRST.search(text) or _FIRST.search(raw):
        return _end_note(session, now, False)
    if _LATEST.search(text) or _LATEST.search(raw):
        return _end_note(session, now, True)
    counted = _month_count(text, session, now)
    if counted is not None:
        return counted
    if _COMPARE.search(text) and re.search(r"\b(?:month|week|writing)\b", text):
        return _compare(text, session, now, first_day)
    if _SUMMARY.search(text) and re.search(r"\b(?:month|week|going|doing)\b", text):
        return _summary(text, session, now, first_day)
    fallback = ns.answer(text, session) if text else None
    return fallback or StatAnswer("none", HELP_LINE)
