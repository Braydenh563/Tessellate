"""The four rules of CHAT_PLAN A15 that `insights.py` does not hold: time of
day, first and last mention, co-occurrence and silence (L-chat-92). Each is a
measurement over the dated notes with a typed template (`composer_tables.
INSIGHT_TEMPLATES`), never a claim, and silent below its threshold."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from tessellate.ai import recognise
from tessellate.ai.insights import (
    DRIFT_DAYS,
    MIN_NOTES,
    TIME_OF_DAY_MIN,
    Insight,
    _day,
    _fill,
    _holds,
    _PLAIN,
    _written,
)

#: Two notes naming each other are enough to say they come up together.
TOGETHER_MIN = 2
_WHEN = {"evening": "you wrote after work", "morning": "you wrote in the morning"}
_NAME = re.compile(r"(?<=[a-z,] )[A-Z][a-z]{2,}\b")


def _holding(subject: str, notes: list[dict]) -> list[tuple[date, dict]]:
    return sorted(((d, n) for n in notes if _holds(n, subject) and (d := _written(n))), key=lambda pair: pair[0])


def time_of_day(subject: str, notes: list[dict], today: date) -> Insight | None:  # noqa: ARG001
    """The part of the day most of `subject`'s notes say they were written in
    ("after work", "in the morning"), when at least `TIME_OF_DAY_MIN` agree."""
    held = _holding(subject, notes)
    parts = Counter(p for _d, n in held if (p := recognise.part_of_day(str(n.get("content") or ""))))
    if not parts:
        return None
    part, count = parts.most_common(1)[0]
    if count < TIME_OF_DAY_MIN:
        return None
    slots = {"subject": subject, "count": count, "total": len(held), "when": _WHEN[part]}
    return Insight("time_of_day", _fill("time_of_day", slots), [n["id"] for _d, n in held], slots)


def span(subject: str, notes: list[dict], today: date) -> Insight | None:
    """The first and the last day `subject` was written about, with how many notes."""
    held = _holding(subject, notes)
    if len(held) < 2 or held[0][0] == held[-1][0]:
        return None
    slots = {"subject": subject, "first": _day(held[0][0], today), "last": _day(held[-1][0], today), "count": len(held)}
    return Insight("span", _fill("span", slots), [n["id"] for _d, n in held], slots)


def _names(note: dict) -> set[str]:
    found = {str(t).lower() for t in note.get("tags") or []}
    return found | {m.group(0).lower() for m in _NAME.finditer(str(note.get("content") or ""))}


def together(subject: str, notes: list[dict], today: date) -> Insight | None:  # noqa: ARG001
    """The tag or name that most often shares a note with `subject`."""
    held = _holding(subject, notes)
    own = set(subject.lower().split())
    counts: Counter = Counter()
    for _d, n in held:
        counts.update(w for w in _names(n) - own if w not in _PLAIN and w not in subject.lower())
    if not counts:
        return None
    other, count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    if count < TOGETHER_MIN:
        return None
    #: A name reads as written ("Sam"); a tag stays as filed.
    shown = next((m.group(0) for _d, n in held for m in _NAME.finditer(str(n.get("content") or "")) if m.group(0).lower() == other), other)
    slots = {"subject": subject, "other": shown, "count": count}
    return Insight("together", _fill("together", slots), [n["id"] for _d, n in held if other in _names(n)], slots)


def silence(subject: str, notes: list[dict], today: date) -> Insight | None:
    """`subject` written about at least `MIN_NOTES - 1` times and not for `DRIFT_DAYS`."""
    held = _holding(subject, notes)
    if len(held) < MIN_NOTES - 1 or (today - held[-1][0]).days < DRIFT_DAYS:
        return None
    slots = {"subject": subject, "last": _day(held[-1][0], today)}
    return Insight("silence", _fill("silence", slots), [n["id"] for _d, n in held], slots)


def quiet_tags(notes: list[dict], today: date, limit: int = 4) -> list[Insight]:
    """Each tag the person wrote under at least twice and has not for a month, the most written under first."""
    tags = Counter(str(t).lower() for n in notes for t in set(n.get("tags") or []))
    found = [i for tag, _c in tags.most_common() if (i := silence(tag, [n for n in notes if tag in {str(t).lower() for t in n.get("tags") or []}], today))]
    return sorted(found, key=lambda i: len(i.note_ids), reverse=True)[:limit]
