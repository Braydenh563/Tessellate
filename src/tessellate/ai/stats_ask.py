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
from tessellate.ai import note_order, recognise
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

#: Two examples, not the capability paragraph: "hello" and every unknown got the whole list (second audit, composed list).
HELP_LINE = 'I did not catch which figure you mean. Try "summarise my month" or "when did I write my first note".'



def _end_note(session: Session, now: datetime, newest: bool) -> StatAnswer:
    """The first or newest visible note, by date and title: the shared reader
    in `ai/note_order.py`, as plain words (this box draws no links)."""
    text, _ = note_order.say(session, note_order.Ask(1, newest), now.tzinfo, linked=False)
    return StatAnswer("latest-note" if newest else "first-note", text)


def _ends(text: str, raw: str, session: Session, now: datetime) -> StatAnswer | None:
    """The first, newest or nth note: one reader (`ai/note_order.py`)."""
    placed = note_order.read(raw)
    if placed is not None and placed.n > 1:
        return StatAnswer("note-order", note_order.say(session, placed, now.tzinfo, linked=False)[0])
    #: The raw words too: the spelling pass turns "start" into "stats".
    if placed is not None and not placed.newest or _FIRST.search(text) or _FIRST.search(raw):
        return _end_note(session, now, False)
    if placed is not None or _LATEST.search(text) or _LATEST.search(raw):
        return _end_note(session, now, True)
    return None


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


#: A yes or no leads only when the question asked one ("am I", "did I", "have I").
_YES_NO = re.compile(r"^(?:am|are|did|have|has|was|were|do|is) (?:i|we|my)\b")


def _compare(text: str, session: Session, now: datetime, first_day: int) -> StatAnswer:
    if _period(text) == "week":
        this_start = ns.week_start(now, first_day)
        last_start = this_start - timedelta(days=7)
        #: Whole days, as the month: Mon to today against Mon to the same weekday.
        stretch = min(last_start + timedelta(days=(now.date() - this_start.date()).days + 1), this_start)
        here = _span(session, this_start, now + timedelta(seconds=1))
        before = _span(session, last_start, stretch)
        whole = _span(session, last_start, this_start)
        label_now, label_before = "this week", "the same day last week"
        verdict_text = (
            f"This week so far you have made {ns._plural(here['notes'], 'note')}, against {before['notes']} by the same day last week "
            f"({whole['notes']} in all of last week). Words written: {here['words']:,} against {before['words']:,}."
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
    lead = ("Yes. " if diff > 0 else "About the same. " if diff == 0 else "Not so far. ") if _YES_NO.match(text) else ""
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
        #: A tag on one or two notes is not a finding.
        if n >= 3:
            text_out += f" Most used tag: {tag} ({ns._plural(n, 'note')})."
    #: Whole days, as `_compare`: the same point is the same day, not the same hour.
    before = _span(session, previous, min(previous + timedelta(days=(now.date() - start.date()).days + 1), start))
    gap = here["notes"] - before["notes"]
    same = "week" if _period(text) == "week" else "month"
    if gap:
        text_out += f" That is {ns._plural(abs(gap), 'note')} {'more' if gap > 0 else 'fewer'} than by the same point last {same}."
    return StatAnswer(
        "summary",
        text_out,
        [
            {"label": "notes", "count": here["notes"]},
            {"label": "words", "count": here["words"]},
            {"label": "reminders done", "count": here["reminders_done"]},
        ],
    )


_LINKS = re.compile(r"\b(?:how many|number of|count)\b.*\blinks?\b|\blinks? (?:count|total)\b")
_ORPHANS = re.compile(r"\borphans?\b|\bunlinked\b|\bno links?\b|not linked")
_STREAK = re.compile(r"\bstreak\b")
_AVERAGE = re.compile(r"\b(?:average|avg|mean|typical)\b.*\b(?:words?|length|long)\b|\bwords? per note\b")
_BUSIEST = re.compile(r"\bbusiest\b|\bmost active\b|\bwhich day\b")
_DID_I = re.compile(r"^(?:did|have) i (?:write|wrote|written|make|made|add|added|take|took)\b")
_UNUSED = re.compile(r"\b(?:haven.?t|have not|never|not) (?:i )?(?:used|tried|opened)\b|\bunused\b|\bwhat (?:do|did) i(?: not| never)? (?:use|used)\b.*\bnever\b")
_NOUN = re.compile(r"\b(?:tags?|categor(?:y|ies)|folders?|spaces?)\b")


def _links(session: Session, now: datetime, _usage: dict) -> StatAnswer:
    n = ns._notebook_block(session, now)["links"]
    return StatAnswer("links", f"You have {ns._plural(n, 'link')} between your notes.", [{"label": "links", "count": n}])


def _streak_run(session: Session, now: datetime, _usage: dict) -> StatAnswer:
    from tessellate.ai import activity_new

    return activity_new.streak(session, now, False)


def _average(session: Session, now: datetime, _usage: dict) -> StatAnswer:
    block = ns._notebook_block(session, now)
    if not block["notes"]:
        return StatAnswer("average", "You have no notes yet.")
    each = round(block["words"] / block["notes"])
    return StatAnswer("average", f"Your notes average {ns._plural(each, 'word')} each, across {ns._plural(block['notes'], 'note')}.", [{"label": "words per note", "count": each}])


def _did_i(session: Session, now: datetime, text: str) -> StatAnswer | None:
    """"did I write yesterday": the day is the recogniser's (a day, not a month or week)."""
    for start, end, _ in recognise.find(text):
        found = recognise.span(text[start:end], now.date(), "past")
        if found and found[2] == "day":
            said = text[start:end].strip()
            begin = _midnight(found[0], now.tzinfo)
            n = _span(session, begin, begin + timedelta(days=1))["notes"]
            return StatAnswer("did-i", f"Yes, {ns._plural(n, 'note')} {said}." if n else f"No notes {said}.", [{"label": said, "count": n}])
    return None


def _unused(_session: Session, _now: datetime, usage_summary: dict) -> StatAnswer:
    names = [_feature(n) for n in (usage_summary.get("unused") or [])]
    days = usage_summary.get("unused_days") or 90
    if not names:
        return StatAnswer("unused", f"You have used every feature in the last {days} days.")
    return StatAnswer("unused", f"Not used in {days} days: {', '.join(names[:8])}.", [{"label": n, "count": 0} for n in names[:8]])


#: First match wins: what the Statistics page shows and the box used to answer
#: with its capability line (G9).
_FIGURES = (
    (_ORPHANS, lambda session, _now, _usage: ns._orphans(session)),
    (_LINKS, _links),
    (_STREAK, _streak_run),
    (_AVERAGE, _average),
    (_BUSIEST, lambda session, _now, _usage: ns._busiest(session)),
    (_UNUSED, _unused),
)


def _page_figure(text: str, session: Session, now: datetime, usage_summary: dict) -> StatAnswer | None:
    if _DID_I.match(text) and (said := _did_i(session, now, text)) is not None:
        return said
    reader = next((read for pattern, read in _FIGURES if pattern.search(text)), None)
    return reader(session, now, usage_summary) if reader else None


def ask(question: str, session: Session, now: datetime, usage_summary: dict, first_day: int = 0) -> StatAnswer:
    """The answer to one question about the page's figures; never raises for
    a question it cannot count, it says what it can."""
    raw = (question or "").strip().lower()
    text = ns._despell(raw)
    figure = _page_figure(text, session, now, usage_summary)
    if figure is not None:
        return figure
    #: A noun the notebook counts (tag, category) wins over the usage verb:
    #: "my most used tag" is a tag question.
    if _USAGE.search(text) and not _NOUN.search(text):
        return _usage(usage_summary)
    ends = _ends(text, raw, session, now)
    if ends is not None:
        return ends
    counted = _month_count(text, session, now)
    if counted is not None:
        return counted
    if _COMPARE.search(text) and re.search(r"\b(?:month|week|writing)\b", text):
        return _compare(text, session, now, first_day)
    if _SUMMARY.search(text) and re.search(r"\b(?:month|week|going|doing)\b", text):
        return _summary(text, session, now, first_day)
    fallback = ns.answer(text, session) if text else None
    return fallback or StatAnswer("none", HELP_LINE)
