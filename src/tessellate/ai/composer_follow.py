"""Follow-ups to a deadlines or plan answer, with no model: "the second one"
and "why" (composer3's leftovers, INBOX 1351).

The dialogue is the only state. The last answer's bullet lines are parsed back
into items (a reminder, or a note's sentence with its note link) and the
notes are read again for the rest. Every clause is an item's own words, a note
title, a date worked out from the note's `created_at`, or a template phrase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from tessellate.ai import recognise
from tessellate.ai.composer_study import Ctx, Reply, pick

_ITEM = re.compile(r"^- (?P<text>.+?)(?: \(\[(?P<title>[^\]]+)\]\(#/notes/(?P<id>\d+)\)\)| \(reminder(?:, (?P<rest>[^)]*))?\))$")
_HEAD = re.compile(r"^\*\*(?P<head>[^*]+)\*\*$")
_UNTIL = re.compile(r"From (?:your reminder|\[(?P<title>[^\]]+)\]\(#/notes/(?P<id>\d+)\))\.\n\n“(?P<text>.+)”", re.S)

_ORD = {"first": 0, "1st": 0, "1": 0, "second": 1, "2nd": 1, "2": 1, "third": 2, "3rd": 2, "3": 2, "fourth": 3, "4th": 3, "4": 3, "fifth": 4, "5th": 4, "5": 4, "sixth": 5, "6th": 5, "6": 5, "seventh": 6, "7th": 6, "7": 6, "last": -1}
_NTH = re.compile(
    r"^(?:(?:ok(?:ay)?|and|so|now|what about|how about|tell me (?:more )?about|more (?:on|about)|explain|expand on|show me|what(?:'s| is)|details? (?:on|of|for))[, ]+)*"
    r"(?:the |number |no\.? |#)?(?P<n>first|second|third|fourth|fifth|sixth|seventh|last|1st|2nd|3rd|4th|5th|6th|7th|[1-7])"
    r"(?: one| item| thing| line| point| reminder| note| deadline)?\s*(?:please|then)?\W*$", re.I)
_WHY = re.compile(
    r"^(?:(?:and|but|so|ok(?:ay)?)[, ]+)*(?:why|how come|why (?:those|these|them)|why (?:is|are) (?:that|it|this|those|these)(?: (?:on there|on the list|listed|there|due|in there|coming up|here))?|"
    r"why (?:did you|have you) (?:pick|choose|list|include|say|show) (?:those|these|that|them|it)|where (?:is|does|did) (?:that|it|this|each) (?:come|coming) from|where did (?:that|those|these|you get that) come from)\W*$", re.I)

PHRASES = {
    "item": (
        "That one is **{text}**.",
        "Number {n}: **{text}**.",
        "Here is item {n}: **{text}**.",
        "Item {n} reads: **{text}**.",
    ),
    "from": (
        "It comes from [{title}](#/notes/{id}), written {written}.",
        "Your note [{title}](#/notes/{id}) has it, saved {written}.",
        "The source is [{title}](#/notes/{id}) from {written}.",
    ),
    "reminder": (
        "It is a reminder you set{rest}.",
        "That is one of your reminders{rest}.",
        "You made this reminder yourself{rest}.",
    ),
    "relative": (
        "The note says it in relative words, so the day is read against {written}, when it was written.",
        "Its day is worked out from {written}, the day the note was written, because the sentence does not give a date.",
        "It names the day loosely, so it counts from {written}, the day you wrote it.",
    ),
    "plain": (
        "The sentence names its own day.",
        "It gives the date in full.",
    ),
    "why_head": (
        "Each line is something you saved, nothing is guessed:",
        "Everything above comes from two places in your own notebook:",
        "These come from two places, your reminders and your notes:",
    ),
    "why_one": (
        "Because [{title}](#/notes/{id}) says: “{text}”",
        "Because your note [{title}](#/notes/{id}) has this line: “{text}”",
        "The reason is in [{title}](#/notes/{id}): “{text}”",
    ),
    "why_reminder": (
        "Because you set a reminder for it.",
        "Because it is one of your own reminders.",
    ),
    "gone": (
        "That note is no longer there, so I can not read more of it.",
        "The note behind that line has changed or gone since.",
    ),
}


@dataclass
class Item:
    text: str
    title: str = ""
    note_id: int | None = None
    rest: str = ""
    day: str = ""

    @property
    def reminder(self) -> bool:
        return self.note_id is None


def items(answer: str) -> list[Item]:
    """The bullet lines of a deadlines or plan answer, each with the day
    heading it sat under."""
    out: list[Item] = []
    day = ""
    for line in (answer or "").splitlines():
        head = _HEAD.match(line.strip())
        if head:
            #: "Today, Wednesday 21 October" is the day after the comma; "Overdue" has none.
            day = head.group("head").split(", ", 1)[-1] if any(c.isdigit() for c in head.group("head")) else ""
            continue
        m = _ITEM.match(line.strip())
        if m and (m.group("id") or "(reminder" in line):
            out.append(Item(m.group("text"), m.group("title") or "", int(m.group("id")) if m.group("id") else None, (m.group("rest") or "").strip(), day))
    return out


def _note(ctx: Ctx, note_id: int | None) -> dict | None:
    return next((n for n in ctx.notes if n.get("id") == note_id), None)


def _written(note: dict | None) -> str:
    made = (note or {}).get("created_at")
    return f"{made:%A} {made.day} {made:%B}" if isinstance(made, datetime) else "an earlier day"


def _how_read(ctx: Ctx, item: Item, note: dict | None) -> str:
    made = (note or {}).get("created_at")
    if recognise.states_its_date(item.text, made if isinstance(made, datetime) else ctx.now):
        return pick(ctx.seed, "fl-plain", PHRASES["plain"])
    return pick(ctx.seed, "fl-rel", PHRASES["relative"]).format(written=_written(note))


def _item_reply(ctx: Ctx, item: Item, n: int) -> Reply:
    lines = [pick(ctx.seed, "fl-item", PHRASES["item"]).format(text=item.text, n=n)]
    if item.reminder:
        rest = f" ({item.rest})" if item.rest else ""
        lines.append(pick(ctx.seed, "fl-rem", PHRASES["reminder"]).format(rest=rest))
        return Reply(" ".join(lines))
    note = _note(ctx, item.note_id)
    if note is None:
        return Reply(" ".join(lines + [pick(ctx.seed, "fl-gone", PHRASES["gone"])]))
    day = f" It falls on {item.day}." if item.day else ""
    lines.append(pick(ctx.seed, "fl-from", PHRASES["from"]).format(title=item.title, id=item.note_id, written=_written(note)) + day)
    lines.append(_how_read(ctx, item, note))
    return Reply(" ".join(lines))


def nth(ctx: Ctx) -> Reply | None:
    """"The second one" after a deadlines or plan answer."""
    found = _NTH.match(" ".join((ctx.asked or ctx.question or "").split()))
    listed = items(ctx.last_answer) if found else []
    if not listed:
        return None
    index = _ORD[found.group("n").lower()]
    if index >= len(listed):
        return Reply(f"My last answer listed {len(listed)} item{'s' if len(listed) != 1 else ''}, so there is no number {index + 1}.")
    return _item_reply(ctx, listed[index], (index if index >= 0 else len(listed) - 1) + 1)


def _why_until(ctx: Ctx) -> Reply | None:
    m = _UNTIL.search(ctx.last_answer)
    if not m:
        return None
    if not m.group("id"):
        return Reply(pick(ctx.seed, "fl-whyrem", PHRASES["why_reminder"]) + f" It reads: “{m.group('text')}”")
    return Reply(pick(ctx.seed, "fl-whyone", PHRASES["why_one"]).format(title=m.group("title"), id=m.group("id"), text=m.group("text")))


def why(ctx: Ctx) -> Reply | None:
    """"Why" after a deadlines, plan or countdown answer: where the lines
    came from, with a note's own sentence for each of up to three."""
    if not _WHY.match(" ".join((ctx.asked or ctx.question or "").split())):
        return None
    listed = items(ctx.last_answer)
    if not listed:
        return _why_until(ctx)
    from_notes = [i for i in listed if not i.reminder]
    reminders = len(listed) - len(from_notes)
    head = pick(ctx.seed, "fl-whyhead", PHRASES["why_head"])
    counts = f"{reminders} reminder{'s' if reminders != 1 else ''} you set and {len(from_notes)} dated sentence{'s' if len(from_notes) != 1 else ''} in your notes."
    lines = [f"{head} {counts}", ""]
    for i, item in enumerate(from_notes[:3]):
        lines.append("- " + pick(ctx.seed, f"fl-why{i}", PHRASES["why_one"]).format(title=item.title, id=item.note_id, text=item.text))
    if reminders and not from_notes:
        lines.append(pick(ctx.seed, "fl-whyrem", PHRASES["why_reminder"]))
    lines += ["", "A sentence that says “Friday” is read against the day its note was written, not today."]
    return Reply("\n".join(lines))


def answer(ctx: Ctx) -> Reply | None:
    return nth(ctx) or why(ctx)
