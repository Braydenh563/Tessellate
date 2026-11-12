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
PER_KIND = {"reminder": 2, "sum": 2, "link": 2, "filing": lexical_filing.CHOICES}
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
#: The amount may be left off ("Total:" and nothing after): the offer then writes it.
_TOTAL = re.compile(rf"^[ \t]*[*_]*(?:total|sum|subtotal)[ \t]*[:=][*_]*[ \t]*([£$€]?)[ \t]*(-?{_NUM})?[ \t]*$", re.I | re.M)
#: A sum written alone on its line with no "=": "12 + 30", "- 4.5 * 3 ?". The operators
#: stand apart from the numbers, so a range ("3-4 days") or a date is never read as one.
_BARE_SUM = re.compile(rf"^[ \t]*(?:[-*+][ \t]+)?({_NUM}(?:[ \t]+[-+*/×x][ \t]+{_NUM})+)[ \t]*\??[ \t]*$", re.M)
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


def _sum_offer(found: re.Match, worked: float, said: str | None, bare: bool) -> dict:
    """The offer for one sum: the answer replaced when one was written, else added
    after the expression (after "=" when it has one, with " = " when it has none)."""
    right = arithmetic.spoken(worked).replace(",", "")
    expr = re.sub(r"\s+", " ", found.group(1))
    if said is not None:
        start, end, replace = found.start(2), found.end(2), right
    else:
        start = end = found.end(1) if bare else found.end()
        replace = f" = {right}" if bare else f" {right}"
    return {
        "kind": "sum", "start": start, "end": end, "said": said or "",
        "label": f"{expr} = {right}",
        "reason": f"{expr} is {right}, not {said}" if said is not None else f"{expr} is {right}",
        "value": {"replace": replace},
    }


def _sums(text: str, quoted: list) -> list[dict]:
    """A sum written with its answer is checked; one written with "=" and no answer, or
    alone on its line with no "=", is offered its answer."""
    out = []
    for found in [*_SUM.finditer(text), *_BARE_SUM.finditer(text)]:
        if _inside(found.start(), found.end(), quoted):
            continue
        try:
            worked = arithmetic.evaluate(found.group(1))
        except arithmetic.NotArithmetic:
            continue
        bare = found.re is _BARE_SUM
        said = None if bare else found.group(2)
        if said is None or abs(float(said) - worked) >= 1e-9:
            out.append(_sum_offer(found, worked, said, bare))
    return out


def _column_above(text: str, at: int) -> list[str]:
    """The amounts on the lines above `at`, back to a blank or a line with none."""
    amounts = []
    for line in reversed(text[:at].rstrip("\n").split("\n")):
        amount = _AMOUNT_LINE.search(line)
        if not line.strip() or amount is None:
            break
        amounts.append(amount.group(1))
    return amounts


def _total_offer(found: re.Match, amounts: list[str], worked: float, said: str | None) -> dict:
    #: Written to the places the column is written to: £6.70, not £6.7.
    places = max(len(a.partition(".")[2]) for a in [*amounts, said or ""])
    right = f"{worked:.{places}f}"
    if said is None:
        spaced = found.group(1) or found.group(0).endswith(" ")
        start = end = found.end()
        replace = right if spaced else " " + right
    else:
        start, end, replace = found.start(2), found.end(2), right
    return {
        "kind": "sum", "start": start, "end": end, "said": said or "",
        "label": f"Total = {found.group(1)}{right}",
        "reason": f"the {len(amounts)} amounts above add up to {right}" + ("" if said is None else f", not {said}"),
        "value": {"replace": replace},
    }


def _totals(text: str, quoted: list) -> list[dict]:
    """A "Total:" line that does not add up the amounts listed above it, or has no
    amount yet."""
    out = []
    for found in _TOTAL.finditer(text):
        amounts = [] if _inside(found.start(), found.end(), quoted) else _column_above(text, found.start())
        worked = sum(float(a) for a in amounts)
        said = found.group(2)
        if len(amounts) >= TOTAL_MIN_AMOUNTS and (said is None or abs(float(said) - worked) >= 1e-9):
            out.append(_total_offer(found, amounts, worked, said))
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
    from tessellate.entry.manager_wiki import find_by_wiki_name

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
    """The one filing decision (`lexical_filing.filing_call`, INBOX 1583):
    "File in X" where a save would file it (`decided`), else the two or three
    choices it waits on, each with the words that put it forward. Nothing once
    the person has picked one of them."""
    if len(text.strip()) < FILING_MIN_CHARS:
        return []
    call = lexical_filing.filing_call(session, text, exclude_entry_id=entry_id)
    if category and category in {name for name, _ in call.candidates}:
        return []
    if call.category:
        picks = [(call.category, call.why)]
    else:
        picks = [(name, f"{why} {call.why}") for name, why in call.choices]
    #: `waits`: the one line the row says for choices ("A close call between ...").
    return [{"kind": "filing", "start": -1, "end": -1, "said": "", "label": f"File in {name}", "reason": why,
             "waits": "" if call.category else call.why,
             "value": {"category": name, "decided": bool(call.category)}} for name, why in picks]


def offers(session: Session, text: str, *, now: datetime, entry_id: int | None = None,
           category: str | None = None, locale: str | None = None, title: str = "") -> list[dict]:
    """The editor's offers for `text`, in the order the row shows them. A
    `title` is filed with the text, as a save files it, and offered on never."""
    text = str(text or "")
    if not text.strip():
        return []
    quoted = quoted_ranges(text)
    spans = recognise.recognise(text, now=now, locale=locale or "en-GB")
    found = (_reminders(text, spans, now, quoted) + _sums(text, quoted) + _totals(text, quoted)
             + _links(session, text, spans, quoted, entry_id)
             + _filing(session, f"# {title.strip()}\n\n{text}" if title.strip() else text, entry_id, category))
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
