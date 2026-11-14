"""Counters (CHAT_PLAN T8, L-chat-122): "add 1 to coffee", "how many coffees this week".

A counter is a note titled "Counter: coffee" with one dated line per change
("- 2026-11-14: +1"). Nothing is stored apart from that note, so the count over
a window is derived from its lines, the note can be read and corrected by hand,
and Undo is the note edit's own. The act waits for Confirm like every write
(`surface_acts` plans it); the question is a computed answer (`composer_quick`)
that says which note it read. No model is involved in either.
"""

from __future__ import annotations

import re
from datetime import date

from tessellate.ai.composer_clock import clean, computed
from tessellate.ai.composer_study import Ctx, Reply

PREFIX = "Counter: "
_WORDS = {"a": 1, "an": 1, "one": 1, "another": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_N = r"(?P<n>\d{1,4}|a|an|one|another|two|three|four|five|six|seven|eight|nine|ten)"
_NAME = r"(?P<name>[a-z][a-z' -]{1,40}?)"
_LEAD = r"^(?:please |pls |can you |could you )*"
_ADD = re.compile(rf"{_LEAD}(?:add|put|give) {_N} (?:more )?(?:to|onto) (?:my |the )?{_NAME}(?: counter| tally| count)?[.!]*$", re.I)
_COUNT = re.compile(rf"{_LEAD}(?:count|tally) {_N} {_NAME}[.!]*$", re.I)
_PLUS = re.compile(rf"^\+(?P<n>\d{{1,4}}) {_NAME}[.!]*$", re.I)
#: A list or a note is not a counter: "add 2 to the shopping list" is the append act's.
_NOT_A_COUNTER = re.compile(r"\b(?:list|note|notes|checklist|journal|diary|log|tracker|reminders?|todo|to-do|tasks?|folder|category|tag|board|map)\b", re.I)
_HOW_MANY = re.compile(rf"^how many {_NAME}(?: (?:have|did|do|had|has) (?:i|we) (?:had|have|got|logged|counted|drunk|eaten|done|taken|made|written|read|run|ran|do|log|count|add))?(?: (?P<when>.+))?$", re.I)
_COUNT_OF = re.compile(r"^(?:what(?: is|'s) )?(?:my |the )?(?P<name>[a-z][a-z' -]{1,40}?) (?:counter|tally|count)(?: (?P<when>.+))?$", re.I)
_DAYS = re.compile(r"^(?:\d{4}-\d{2}-\d{2}): ([+-]\d+)\s*$")


def key(name: str) -> str:
    """"Coffees", "coffee" and "my coffee counter" are one counter."""
    low = re.sub(r"^(?:my|the|our)\s+", "", (name or "").strip().lower())
    low = re.sub(r"\s+(?:counter|tally|count)$", "", low)
    if len(low) > 3 and low.endswith("ies"):
        return low[:-3] + "y"
    return low[:-1] if len(low) > 3 and low.endswith("s") and not low.endswith("ss") else low


def read(text: str) -> dict | None:
    """The act `text` is ("add 2 to coffee"), or None."""
    said = " ".join((text or "").split())
    for pattern in (_ADD, _COUNT, _PLUS):
        found = pattern.match(said)
        if not found:
            continue
        name = found.group("name").strip(" '-")
        if _NOT_A_COUNTER.search(name) or not name:
            return None
        raw = found.group("n").lower()
        n = int(raw) if raw.isdigit() else _WORDS[raw]
        if 0 < n < 10000:
            return {"intent": "counter", "name": key(name), "shown": name.lower(), "n": n}
    return None


def title_of(note: dict) -> str:
    first = next((line.strip() for line in str(note.get("content") or "").splitlines() if line.strip()), "")
    return first.lstrip("# ").strip()


def find(notes: list[dict], name: str) -> dict | None:
    for note in notes:
        title = title_of(note)
        if title.lower().startswith(PREFIX.lower()) and key(title[len(PREFIX):]) == key(name):
            return note
    return None


def line_for(n: int, today: date) -> str:
    return f"- {today.isoformat()}: +{n}"


def new_content(name: str, n: int, today: date) -> str:
    return f"# {PREFIX}{name}\n\n{line_for(n, today)}"


def total(note: dict, since: date | None = None, until: date | None = None) -> int:
    """The sum of the note's dated lines inside the window (the whole note when none)."""
    count = 0
    for raw in str(note.get("content") or "").splitlines():
        found = _DAYS.match(raw.strip().lstrip("-* ").strip())
        if not found:
            continue
        day = date.fromisoformat(raw.strip().lstrip("-* ")[:10])
        if (since is None or day >= since) and (until is None or day <= until):
            count += int(found.group(1))
    return count


def answer(ctx: Ctx) -> Reply | None:
    """"how many coffees this week", "my coffee counter": the note's lines summed over the window."""
    text = clean(ctx.question)
    found = _HOW_MANY.match(text) or _COUNT_OF.match(text)
    if not found or len(text) > 100:
        return None
    note = find(ctx.notes, found.group("name"))
    if note is None:
        return None
    from tessellate.search import query

    today = ctx.now.date()
    when = (found.group("when") or "").strip()
    since = until = None
    said = "in all"
    if when:
        window = query.understand(f"x {when}", today)
        if window.since is None:
            return None
        since, until, said = window.since, window.until, when
    n = total(note, since, until)
    title = title_of(note)
    return computed(
        f"{n} {found.group('name').strip()}, {said}." if when else f"{n} {found.group('name').strip()} so far, {said}.",
        f"the dated lines of your note “{title}”" + (f" from {since:%-d %B} to {until:%-d %B %Y}" if since else ""),
    )
