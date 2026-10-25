"""Two more readers of the notes with no model: "what did I write about
<topic> this week" (a dated list) and "outline <note>" (its headings).

Every clause is a note's own sentence, a title, a date or a count worked out
here, or a template phrase (the composer's rule). The window words ("this
week", "last month", "in october") are read by `ai/recognise.py` through
`ai/when.py`; nothing here compiles a date word.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from tessellate.ai import study
from tessellate.ai import when as when_words
from tessellate.ai.composer_study import Ctx, Reply, pick, topic_notes

MAX_LISTED = 8
MAX_OUTLINE = 40

_LEAD = r"(?:(?:please|pls|can you|could you|hey|ok|okay|so|and|tell me|show me|remind me)[, ]+)*"
_WROTE = re.compile(
    rf"^{_LEAD}(?:what|which notes?|anything|everything|all)\s+(?:(?:did|have|had|do)\s+(?:i|we)\s+)?"
    r"(?:write|wrote|written|note|noted|jot|jotted|save|saved|capture|captured|add|added|make|made|record|recorded|put down|type|typed)"
    r"(?:\s+down)?\s+(?:about|on|for|regarding|around|re)\s+(?P<t>.+?)\W*$", re.I)
_WROTE_ANY = re.compile(
    rf"^{_LEAD}(?:what|which notes?|anything)\s+(?:(?:did|have|had|do)\s+(?:i|we)\s+)?"
    r"(?:write|wrote|written|note|noted|jot|jotted|save|saved|capture|captured|add|added|make|made|record|recorded|put down|type|typed)"
    r"(?:\s+down)?\s+(?P<t>(?:in|on|during|over|from|since|for|this|last)\b.*?)\W*$", re.I)
_NOTES_ON = re.compile(
    rf"^{_LEAD}(?:show|list|find|get|give)?\s*(?:me\s+)?(?:all\s+)?(?:my\s+)?(?:the\s+)?notes?\s+(?:i\s+(?:wrote|made|saved|took|jotted)\s+)?(?:about|on|for|regarding)\s+(?P<t>.+?)\W*$", re.I)
_OUTLINE = re.compile(
    rf"^{_LEAD}(?:(?:give|show|make|write|draw|build)\s+(?:me\s+)?(?:an?\s+|the\s+)?)?(?:outline|structure|table of contents|contents|headings|skeleton|sections|toc)"
    r"(?:\s+(?:of|for|from|in|to))?\s*(?P<t>.*?)\W*$|"
    rf"^{_LEAD}(?:outline|structure)\s+(?P<u>.+?)\W*$|"
    rf"^{_LEAD}what\s+(?:sections|headings|parts)\s+(?:does|do|are in|are there in)\s+(?P<v>.+?)(?:\s+have|\s+hold|\s+contain)?\W*$", re.I)

PHRASES = {
    "recent_head": (
        "You wrote about {topic} in {n} note{s} {span}:",
        "{n} note{s} {span} mention{v} {topic}:",
        "{Span}, {topic} comes up in {n} note{s}:",
        "Here is what you saved on {topic} {span}, {n} in all:",
    ),
    "recent_none": (
        "You did not write anything about {topic} {span}.",
        "No note {span} mentions {topic}.",
        "Nothing {span} touches {topic}.",
    ),
    "recent_last": (
        "The latest note on it is {link}, from {day}.",
        "The last time you wrote about it was {day}, in {link}.",
        "Your most recent note on it is {link} ({day}).",
    ),
    "recent_more": (
        "And {n} more.",
        "{n} more are not shown.",
    ),
    "outline_head": (
        "{link} has {n} section{s}:",
        "The outline of {link}, {n} heading{s}:",
        "Here is how {link} is laid out, {n} heading{s}:",
        "{link} runs through {n} heading{s}:",
    ),
    "outline_none": (
        "{link} has no headings to outline. It opens with: “{first}”",
        "There are no headings in {link}, so there is no outline. Its first line: “{first}”",
    ),
    "outline_more": (
        "And {n} more headings.",
        "{n} more headings follow.",
    ),
    "outline_tail": (
        "About {words} words in all.",
        "{words} words in all.",
    ),
}


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


def _link(note: dict) -> str:
    return f"[**{study.title_of(str(note.get('content') or '')) or 'Untitled'}**](#/notes/{note['id']})"


def _day(made: object) -> str:
    return f"{made:%a} {made.day} {made:%b}" if isinstance(made, datetime) else "an earlier day"


# --- what did I write about X this week ----------------------------------------------------

def _window(text: str, today: date) -> tuple[date, date, str, str] | None:
    """(first day, last day, how it was said, the text without it)."""
    low = text.lower()
    for s, e, phrase in when_words.find(low):
        span = when_words.span(phrase, today, "past")
        if span:
            rest = (text[:s] + " " + text[e:]).strip(" ,.?")
            rest = re.sub(r"\b(?:from|during|in|over|within|for|since|on|of|at)\s*$", "", rest, flags=re.I).strip(" ,.?")
            return span[0], span[1], phrase, rest
    return None


def _wanted(topic: str) -> list[str]:
    return study.content_stems(re.sub(r"\b(?:my|the|notes?|about|on|of|for|in|from|and|a|an|all|everything|please|stuff|anything)\b", " ", topic, flags=re.I))


def _sentence_with(content: str, wanted: list[str]) -> str:
    sentences = study.sentences(study.clean(content))
    return next((s for s in sentences if all(w in s.lower() for w in wanted)), "") or next((s for s in sentences if any(w in s.lower() for w in wanted)), "")


def _made(note: dict) -> datetime | None:
    made = note.get("created_at")
    return made.replace(tzinfo=None) if isinstance(made, datetime) and made.tzinfo else made if isinstance(made, datetime) else None


def _matching(ctx: Ctx, wanted: list[str], start: date, end: date) -> list[dict]:
    out = []
    for note in ctx.notes:
        made = _made(note)
        if made is None or not start <= made.date() <= end:
            continue
        low = str(note.get("content") or "").lower()
        if all(w in low for w in wanted):
            out.append(note)
    return out


def _item(note: dict, wanted: list[str]) -> str:
    content = str(note.get("content") or "")
    line = _sentence_with(content, wanted)
    title = study.title_of(content)
    body = f": {line}" if line and line.strip().lower() != title.strip().lower() else ""
    return f"- {_day(_made(note))}, [{title or 'Untitled'}](#/notes/{note['id']}){body}"


def _read_recent(ctx: Ctx) -> tuple[list[str], date, date, str, str] | None:
    text = " ".join((ctx.asked or ctx.question or "").split())
    found = _WROTE.match(text) or _NOTES_ON.match(text)
    any_topic = None if found else _WROTE_ANY.match(text)
    window = _window((found or any_topic).group("t"), ctx.now.date()) if (found or any_topic) and len(text) <= 160 else None
    if window is None:
        return None
    start, end, said, topic = window
    wanted = _wanted(topic)
    if any_topic and not wanted:
        return [], start, end, said.strip(), "anything"  # no topic: every note of the window
    return (wanted, start, end, said.strip(), topic.strip() or "that") if wanted else None


def _nothing(ctx: Ctx, wanted: list[str], span: str, shown: str) -> Reply:
    seed = ctx.seed
    lines = [pick(seed, "nt-none", PHRASES["recent_none"]).format(topic=shown, span=span)]
    before = next((n for n in ctx.notes if _made(n) and all(w in str(n.get("content") or "").lower() for w in wanted)), None)
    if before is not None:
        lines.append(pick(seed, "nt-last", PHRASES["recent_last"]).format(link=_link(before), day=_day(_made(before))))
    return Reply(" ".join(lines))


def recent(ctx: Ctx) -> Reply | None:
    read = _read_recent(ctx)
    if read is None:
        return None
    wanted, start, end, span, shown = read
    hits = _matching(ctx, wanted, start, end)
    if not hits:
        return _nothing(ctx, wanted, span, shown)
    n = len(hits)
    head = pick(ctx.seed, "nt-head", PHRASES["recent_head"]).format(
        topic=shown, n=n, s=_plural(n), span=span, Span=span[:1].upper() + span[1:], v="s" if n == 1 else "")
    lines = [head, ""] + [_item(note, wanted) for note in hits[:MAX_LISTED]]
    if n > MAX_LISTED:
        lines += ["", pick(ctx.seed, "nt-more", PHRASES["recent_more"]).format(n=n - MAX_LISTED)]
    return Reply("\n".join(lines))


# --- outline ------------------------------------------------------------------------------

def _heading_lines(content: str) -> list[tuple[int, str, int]]:
    """(level, title, words) for each heading, in order."""
    out = []
    for sec in study.sections(content):
        if sec.level:
            out.append((sec.level, sec.title, len(sec.text.split())))
    return out


def _outline_note(ctx: Ctx) -> dict | None:
    text = " ".join((ctx.asked or ctx.question or "").split())
    found = _OUTLINE.match(text) if len(text) <= 120 else None
    if not found:
        return None
    notes = topic_notes(found.group("t") or found.group("u") or found.group("v") or "", ctx, limit=1)
    return notes[0] if notes else None


def _outline_lines(ctx: Ctx, note: dict, heads: list[tuple[int, str, int]]) -> list[str]:
    seed = ctx.seed
    base = min(level for level, _t, _w in heads)
    lines = [pick(seed, "ol-head", PHRASES["outline_head"]).format(link=_link(note), n=len(heads), s=_plural(len(heads))), ""]
    for level, title, words in heads[:MAX_OUTLINE]:
        lines.append(f"{'  ' * (level - base)}- {title}" + (f" ({words} words)" if words else ""))
    if len(heads) > MAX_OUTLINE:
        lines += ["", pick(seed, "ol-more", PHRASES["outline_more"]).format(n=len(heads) - MAX_OUTLINE)]
    return lines


def outline(ctx: Ctx) -> Reply | None:
    note = _outline_note(ctx)
    if note is None:
        return None
    content = str(note.get("content") or "")
    heads = _heading_lines(content)
    if len(heads) == 1 and heads[0][1] == study.title_of(content):
        heads = []  # the title alone is not an outline
    if not heads:
        first = study.sentences(study.clean(content))[:1]
        return Reply(pick(ctx.seed, "ol-none", PHRASES["outline_none"]).format(link=_link(note), first=(first[0] if first else study.title_of(content))))
    lines = _outline_lines(ctx, note, heads)
    lines += ["", pick(ctx.seed, "ol-tail", PHRASES["outline_tail"]).format(words=len(study.clean(content).split()))]
    return Reply("\n".join(lines), asks=[f"Quiz me on {study.title_of(content)}"])


def answer(ctx: Ctx) -> Reply | None:
    return recent(ctx) or outline(ctx)
