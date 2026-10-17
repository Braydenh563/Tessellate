"""What the note editor offers while you write (CHAT_PLAN section 2, the
note editor row; WORLD_CLASS 23): a day in the text becomes a reminder
offer, a sum written with its answer is checked, a name another note opens
with becomes a `[[link]]` offer, and the filing suggestion comes with its
reason. At most `LIMIT` offers, each pointing at the words it came from.

Nothing here reads language itself: days, people and places are the
recogniser's spans (decision 46), sums are `arithmetic.evaluate`, the
category is `lexical_filing`'s. Quoted words (straight or curly double
quotes, backticks, a fenced block, a `>` line) are someone else's and are
never offered on: "he said \"see you monday\"" sets nothing.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import arithmetic, lexical_filing, recognise

#: The row under the editor holds this many; more is a list nobody reads.
LIMIT = 5
#: Per kind, so one kind cannot fill the row.
PER_KIND = {"reminder": 2, "sum": 2, "link": 2, "filing": 1}
#: Too little text to file: the same floor the tag suggestions use.
FILING_MIN_CHARS = 20
#: A reminder for a day with no time said is set for this hour, and the
#: offer says so.
DEFAULT_HOUR = 9

#: An unclosed fence runs to the end of the text (`\Z`): with `re.M`, `$`
#: ended it at its own first line, so the lines of a code block were offered.
_QUOTED = re.compile(r"```.*?(?:```|\Z)|`[^`\n]*`|\"[^\"\n]*\"|“[^“”\n]*”|^[ \t]*>.*$", re.S | re.M)
_NUM = r"\d+(?:\.\d+)?"
_SUM = re.compile(rf"(?<![\w.])({_NUM}(?:\s*[-+*/×x]\s*{_NUM})+)\s*=\s*(-?{_NUM})?(?![\w.])")
#: A "Total:" line under a column of amounts (OPEN 1100): each line above it,
#: back to a blank line, ends in an amount, with an optional currency sign.
_TOTAL = re.compile(rf"^[ \t]*[*_]*(?:total|sum|subtotal)[ \t]*[:=][*_]*[ \t]*([£$€]?)[ \t]*(-?{_NUM})[ \t]*$", re.I | re.M)
_AMOUNT_LINE = re.compile(rf"(?<![\w.])[£$€]?[ \t]*(-?{_NUM})[ \t]*$")
#: Fewer than this is not a column.
TOTAL_MIN_AMOUNTS = 2
#: The opening bracket and quote are excluded from a span's body, so a run of `[[` or
#: `“` with no close is read once, not once per start (CodeQL, polynomial).
_LINKED = re.compile(r"\[\[[^\[\]\n]*\]\]")
_SENTENCE_END = re.compile(r"[.!?\n]")
#: `_reminder_words` folds whitespace to one space before this runs.
_DANGLING = re.compile(r" (?:on|at|by|for|from|the) ?$", re.I)


def quoted_ranges(text: str) -> list[tuple[int, int]]:
    """Where `text` quotes someone, as (start, end) pairs."""
    return [(m.start(), m.end()) for m in _QUOTED.finditer(text)]


def _inside(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(s <= start and end <= e for s, e in ranges)


def _sentence(text: str, start: int, end: int) -> tuple[int, int]:
    head = max((m.end() for m in _SENTENCE_END.finditer(text, 0, start)), default=0)
    tail = _SENTENCE_END.search(text, end)
    return head, tail.start() if tail else len(text)


def _reminder_words(text: str, span: recognise.Span) -> str:
    head, tail = _sentence(text, span.start, span.end)
    words = (text[head:span.start] + " " + text[span.end:tail]).strip()
    words = re.sub(r" ([,;:])", r"\1", re.sub(r"\s+", " ", words))
    words = _DANGLING.sub("", words).strip(" ,;:-")
    return words[:120]


def _due(span: recognise.Span, now: datetime) -> tuple[datetime, bool] | None:
    """The moment a reminder for this span is due and whether a time was
    said; None for a day already gone."""
    value = span.value
    if isinstance(value, datetime):
        due, said = value, True
    elif isinstance(value, date):
        due, said = datetime.combine(value, time(DEFAULT_HOUR), tzinfo=now.tzinfo), False
    else:
        return None
    if due.tzinfo is None and now.tzinfo is not None:
        due = due.replace(tzinfo=now.tzinfo)
    return (due, said) if due > now else None


def _reminders(text: str, spans: list[recognise.Span], now: datetime, quoted: list) -> list[dict]:
    out = []
    for span in spans:
        if span.rank or span.kind not in ("date", "datetime") or _inside(span.start, span.end, quoted):
            continue
        due = _due(span, now)
        if due is None:
            continue
        words = _reminder_words(text, span) or "this note"
        when = span.read_as + ("" if due[1] else f" at {DEFAULT_HOUR:02d}:00")
        out.append({
            "kind": "reminder", "start": span.start, "end": span.end, "said": span.text,
            "label": f"Remind me {when}",
            # B72: the reminder is the timeline's row and the calendar's chip; say so.
            "reason": f"“{span.text}” reads as {span.read_as}" + ("" if due[1] else "; no time was said")
            + "; a reminder goes on the timeline and the calendar",
            "value": {"text": words, "due_at": due[0].isoformat(timespec="minutes")},
        })
    return out


def _sums(text: str, quoted: list) -> list[dict]:
    out = []
    for found in _SUM.finditer(text):
        if _inside(found.start(), found.end(), quoted):
            continue
        try:
            worked = arithmetic.evaluate(found.group(1))
        except arithmetic.NotArithmetic:
            continue
        said = found.group(2)
        right = arithmetic.spoken(worked).replace(",", "")
        if said is not None and abs(float(said) - worked) < 1e-9:
            continue
        expr = re.sub(r"\s+", " ", found.group(1))
        start, end = (found.start(2), found.end(2)) if said is not None else (found.end(), found.end())
        out.append({
            "kind": "sum", "start": start, "end": end, "said": said or "",
            "label": f"{expr} = {right}",
            "reason": f"{expr} is {right}, not {said}" if said is not None else f"{expr} is {right}",
            "value": {"replace": right if said is not None else f" {right}"},
        })
    return out


def _totals(text: str, quoted: list) -> list[dict]:
    """A "Total:" line that does not add up the amounts listed above it."""
    out = []
    for found in _TOTAL.finditer(text):
        if _inside(found.start(), found.end(), quoted):
            continue
        amounts = []
        for line in reversed(text[: found.start()].rstrip("\n").split("\n")):
            amount = _AMOUNT_LINE.search(line)
            if not line.strip() or amount is None:
                break
            amounts.append(amount.group(1))
        if len(amounts) < TOTAL_MIN_AMOUNTS:
            continue
        worked = sum(float(a) for a in amounts)
        said = found.group(2)
        if abs(float(said) - worked) < 1e-9:
            continue
        #: Written to the places the column is written to: £6.70, not £6.7.
        places = max(len(a.partition(".")[2]) for a in [*amounts, said])
        right = f"{worked:.{places}f}"
        out.append({
            "kind": "sum", "start": found.start(2), "end": found.end(2), "said": said,
            "label": f"Total = {found.group(1)}{right}",
            "reason": f"the {len(amounts)} amounts above add up to {right}, not {said}",
            "value": {"replace": right},
        })
    return out


def _names(session: Session, text: str, spans: list[recognise.Span]) -> list[tuple[int, int, str]]:
    """(start, end, name) for each person or place the recogniser read and
    each entity the notebook knows, found in `text` as whole words."""
    low = text.lower()
    seen: dict[str, tuple[int, int, str]] = {}
    for span in spans:
        if span.kind in ("person", "place") and not span.rank:
            seen.setdefault(span.text.lower(), (span.start, span.end, span.text))
    from tessellate.core.database import Entity

    for name in session.scalars(select(Entity.name).limit(5000)):
        key = (name or "").strip().lower()
        if len(key) < 3 or key in seen or key not in low:
            continue
        found = re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", low)
        if found:
            seen[key] = (found.start(), found.end(), text[found.start():found.end()])
    return sorted(seen.values())


def _links(session: Session, text: str, spans: list[recognise.Span], quoted: list, entry_id: int | None) -> list[dict]:
    from tessellate.entry.manager import find_by_wiki_name

    linked = [(m.start(), m.end()) for m in _LINKED.finditer(text)]
    out = []
    for start, end, name in _names(session, text, spans):
        if _inside(start, end, quoted) or _inside(start, end, linked):
            continue
        note = find_by_wiki_name(session, name)
        if note is None or note.id == entry_id:
            continue
        opening = re.sub(r"\s+", " ", (note.content or "").lstrip("# ").strip())[:48]
        out.append({
            "kind": "link", "start": start, "end": end, "said": name,
            "label": f"Link [[{name}]]",
            "reason": f"A note opens with “{opening}”",
            "value": {"replace": f"[[{name}]]", "entry_id": note.id},
        })
    return out


def _filing(session: Session, text: str, entry_id: int | None, category: str | None) -> list[dict]:
    if len(text.strip()) < FILING_MIN_CHARS:
        return []
    picks = lexical_filing.suggest_categories_explained(session, text, exclude_entry_id=entry_id, limit=1)
    if not picks or not picks[0][1] or picks[0][0] == category:
        return []
    name, why = picks[0]
    return [{"kind": "filing", "start": -1, "end": -1, "said": "", "label": f"File in {name}", "reason": why,
             "value": {"category": name}}]


def offers(session: Session, text: str, *, now: datetime, entry_id: int | None = None,
           category: str | None = None, locale: str | None = None) -> list[dict]:
    """The editor's offers for `text`, in the order the row shows them."""
    text = str(text or "")
    if not text.strip():
        return []
    quoted = quoted_ranges(text)
    spans = recognise.recognise(text, now=now, locale=locale or "en-GB")
    found = (_reminders(text, spans, now, quoted) + _sums(text, quoted) + _totals(text, quoted)
             + _links(session, text, spans, quoted, entry_id) + _filing(session, text, entry_id, category))
    out: list[dict] = []
    taken: dict[str, int] = {}
    for offer in found:
        if taken.get(offer["kind"], 0) >= PER_KIND[offer["kind"]]:
            continue
        taken[offer["kind"]] = taken.get(offer["kind"], 0) + 1
        out.append(offer)
        if len(out) >= LIMIT:
            break
    return out


def date_chip(text: str, *, now: datetime, locale: str | None = None) -> dict | None:
    """The first day a short text names, for a chip on it (a board's sticky,
    CHAT_PLAN section 2): the words, the day said short ("Fri 16 Oct, 15:00"),
    how it was read, and, for a day still to come, the reminder it offers.
    Quoted words are skipped as in the editor; None when no day is named."""
    text = str(text or "")
    if not text.strip():
        return None
    quoted = quoted_ranges(text)
    for span in recognise.recognise(text, now=now, locale=locale or "en-GB"):
        if span.rank or span.kind not in ("date", "datetime") or _inside(span.start, span.end, quoted):
            continue
        value = span.value
        day = value.date() if isinstance(value, datetime) else value
        short = f"{day:%a} {day.day} {day:%b}" + (f", {value:%H:%M}" if isinstance(value, datetime) else "")
        offer = next(iter(_reminders(text, [span], now, quoted)), None)
        return {"said": span.text, "short": short, "read_as": span.read_as, "start": span.start, "end": span.end,
                "reminder": offer["value"] if offer else None}
    return None
