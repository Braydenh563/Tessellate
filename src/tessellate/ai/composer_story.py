"""An overview written as a few paragraphs, not a column (INBOX 1743).

The owner: "I've always wanted the ask subtab to be a smart browser for your
notes". "What do I know about courses and study" used to retell one
sentence per note, each its own paragraph, with filler between them ("Two
notes more on the right.", "More from ...", "Show six more"). It is now a
lead that names the span and the arc, two or three paragraphs that group
the notes by when they were written (a new paragraph at the biggest gaps),
a read of how the stretch went (a finish is congratulated, a hard week is
acknowledged plainly), and one insight the person did not ask for. Every
sentence that claims something carries one note's row, so each gets one
citation mark; the Matching records stay the browse list.

Rules (the owner's, 1743): a definition is "your X note defines ..." and
never "You mentioned that"; slang and the person's own phrasing are
quoted, never re-voiced; a time opener is never said twice in a row; no
filler line. A model up gets the same rules in `librarian.ASK_OVERVIEW`
(CHAT_PLAN decision 75).
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from datetime import date

#: Fewer notes read better as the lines they were; more are not woven (a
#: paragraph a dozen sentences long is the column again).
MIN_NOTES = 5
MAX_NOTES = 14
MAX_PARAGRAPHS = 3
_NUMBERS = {4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen"}
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

#: Words that say a stretch was hard, or that something was finished.
_HARD = re.compile(r"\b(?:sent home|missed|didn'?t|did not|couldn'?t|struggl\w*|stress\w*|exhaust\w*|tired|behind|overwhelm\w*|late)\b", re.I)
_FINISH = re.compile(r"\b(?:is done|finished|submitted|handed in|graduat\w*|passed|completed)\b", re.I)
#: A note written the way a person talks to themselves: said in quotes.
_SLANG = re.compile(r"\b(?:lol|lmao|haha+|chill|gonna|wanna|ngl|tbh|idk|omg|bruh)\b|[:;]-?[dp)(]\b|[\U0001F300-\U0001FAFF☀-➿]", re.I)
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿️]+")
_SEMESTER = re.compile(r"\b(semester|term|trimester)\b", re.I)
_WEEKDAY = re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)day(s?)\b")
#: A time lead the per-note line starts with; the paragraph says its own.
_LEAD = re.compile(r"^(?:back in [a-z]+|in [a-z]+|on \d{1,2} [a-z]+|(?:[a-z]+ (?:days?|weeks?|months?) (?:ago|later|on))(?:, on \d{1,2} [a-z]+)?|"
                   r"(?:a|one) (?:day|week|month) (?:ago|later|on)(?:, on \d{1,2} [a-z]+)?|yesterday|today|last (?:week|month))\s*,\s*", re.I)
_REPORT = re.compile(r"^you (?:mentioned|said|noted|recorded|put down|jotted down) that ", re.I)
#: Typed without its apostrophe: said back flat ("You didnt lock in") it reads as the app's typo, so it is quoted.
_RAW = re.compile(r"\b(?:didnt|dont|cant|wont|couldnt|wouldnt|isnt|im|ive)\b", re.I)
_DEFINES = re.compile(r"^(?P<term>[^.]{2,60}?) (?:is|are|means|refers to) (?P<what>(?:the|a|an|when|how|any)\b.+)$", re.I | re.S)
_ASIDE = re.compile(r"\s*[–—-]\s[^–—]*?\s[–—-]\s*")


@dataclass
class Plan:
    """The shape of the stretch: its span, its paragraphs, its arc."""

    first: date
    last: date
    chunks: list[list[int]]  # indexes into the notes, oldest first
    arc: str  # "one semester", "a few months", ... or ""


def _gap(a: date, b: date) -> int:
    return (b - a).days


def _chunks(days: list[date]) -> list[list[int]]:
    """Cut the oldest-first days into at most MAX_PARAGRAPHS runs, at the
    biggest gaps, keeping the runs about even (a run of one note is a line)."""
    n = len(days)
    if n < 2 * MIN_NOTES // 2:
        return [list(range(n))]
    best: tuple[float, tuple[int, ...]] | None = None
    for k in range(1, min(MAX_PARAGRAPHS, n // 2)):
        for cuts in itertools.combinations(range(1, n), k):
            edges = (0, *cuts, n)
            sizes = [b - a for a, b in itertools.pairwise(edges)]
            if min(sizes) < 2:
                continue
            cost = sum(abs(s - n / (k + 1)) for s in sizes) * 3 - sum(_gap(days[c - 1], days[c]) for c in cuts)
            if best is None or cost < best[0]:
                best = (cost, edges)
    if best is None:
        return [list(range(n))]
    edges = best[1]
    return [list(range(a, b)) for a, b in itertools.pairwise(edges)]


def _arc(days: list[date], texts: list[str]) -> str:
    months = (days[-1].year - days[0].year) * 12 + days[-1].month - days[0].month
    if any(_SEMESTER.search(t) for t in texts) and 2 <= months <= 6:
        return "one semester"
    return {0: "", 1: "a month or so"}.get(months, f"about {months} months") if months > 0 else ""


def plan(days: list[date], texts: list[str]) -> Plan | None:
    """The plan for notes written on `days` (oldest first), or None when there
    are too few or too many to weave."""
    if not (MIN_NOTES <= len(days) <= MAX_NOTES):
        return None
    return Plan(days[0], days[-1], _chunks(days), _arc(days, texts))


def _month(d: date) -> str:
    return _MONTHS[d.month - 1]


def _part(d: date) -> str:
    return "early " if d.day <= 10 else "mid " if d.day <= 20 else "late "


def span_words(first: date, last: date) -> str:
    """"July to early November": the months, with a part of the last one."""
    if (first.year, first.month) == (last.year, last.month):
        return f"{_part(first).strip()} {_month(first)}".strip() if _part(first) != _part(last) else f"{_part(first)}{_month(first)}"
    year = f" {last.year}" if first.year != last.year else ""
    return f"{_month(first)} to {_part(last)}{_month(last)}{year}"


# --- the sentences ---------------------------------------------------------------


def _lower(clause: str) -> str:
    return clause if re.match(r"I\b|[A-Z]{2,}", clause) else clause[:1].lower() + clause[1:]


def _clean_quote(text: str) -> str:
    """A note's words for a quote: no emoji, no trailing marks."""
    text = re.sub(r"(?:^|\s)[:;]-?[dDpP)(]+(?=\s|$)", "", _EMOJI.sub("", text))
    return re.sub(r"\s+", " ", text).strip().rstrip("!.?:").strip()


def _caps_days(text: str) -> str:
    return _WEEKDAY.sub(lambda m: m.group(0).capitalize(), text)


@dataclass
class Unit:
    """One sentence of the story: its words and the note sentence it cites."""

    view: object
    clause: str  # begins with "you" or "your", no time lead, no stop
    source: object  # the composer_read.Sentence cited
    row: dict | None = None


def clause_of(view, line: str, row: dict | None, dg) -> Unit | None:  # noqa: ANN001
    """The note as a clause: a definition says it defines, slang is quoted,
    an ordinary line loses its time lead and its "you mentioned that"."""
    prose = [s for s in view.sentences if s.kind == "prose"]
    first = prose[0] if prose else (view.sentences[0] if view.sentences else None)
    if first is None:
        return None
    title = (view.title or "").strip().rstrip("…").strip() if view.titled else ""
    defined = _DEFINES.match(_ASIDE.sub(" ", first.text).strip().rstrip("."))
    if title and defined and not re.match(r"(?:i|my|you|we)\b", first.text, re.I) and title.lower().split()[0] in defined.group("term").lower():
        return Unit(view, f"your {title} note defines the term as {_lower(defined.group('what')).strip()}", first)
    quote = _clean_quote(first.text)
    if (_SLANG.search(first.text) or _RAW.search(first.text)) and 0 < len(quote.split()) <= 14:
        return Unit(view, f"you wrote “{quote}”", first)
    if not line:
        return None
    body = _LEAD.sub("", line.strip()).rstrip(".")
    reported = _REPORT.match(body)
    if reported:
        #: "You mentioned that you ..." keeps its clause; "that uni is done" has no "you" to lead and is quoted.
        body = body[reported.end():] if re.match(r"you\b", body[reported.end():], re.I) else "-"
    #: One sentence a unit: the claim is the first, and a second would be uncited.
    body = re.split(r"(?<=[a-z0-9])\.\s+(?=[A-Z])", body, maxsplit=1)[0]
    if not re.match(r"(?:you|your)\b", body, re.I):
        said = _clean_quote(title) if title and len(title.split()) <= 6 else quote
        body = f"you wrote “{said}”"
    source = next((s for s in view.sentences if row and s.start == row.get("start")), first)
    return Unit(view, _caps_days(_lower(body)), source, row)


def _when(prev: date | None, d: date, said: list[str], first: bool) -> str:
    """The time opener for the sentence on `d`: a month, never a count of days
    (INBOX 1441: a day is said only when the question asks about time), and
    never the one just used."""
    if first or prev is None:
        options = [f"In {_month(d)}", f"In {_part(d)}{_month(d)}"]
    elif (prev.year, prev.month) == (d.year, d.month):
        options = ["Soon after", "After that", "Then", "Next"]
    else:
        options = [f"By {_month(d)}", f"Come {_month(d)}", f"In {_month(d)}"]
    return next((o for o in options if o not in said[-2:]), options[0])


def sentence(unit: Unit, opener: str) -> str:
    return f"{opener}, {unit.clause}." if opener else f"{unit.clause[:1].upper()}{unit.clause[1:]}."


def _row(unit: Unit, text: str) -> dict:
    base = dict(unit.row or {})
    base.update({
        "sentence": text.rstrip("."), "note_id": unit.view.note.get("source_id", unit.view.id), "source": unit.source.text,
        "start": unit.source.start, "end": unit.source.end, "score": 1.0, "digest": True, "kind": getattr(unit.view, "kind", "note"),
    })
    base.pop("parts", None)
    return base


def _hard_run(units: list[Unit]) -> list[Unit]:
    return [u for u in units if _HARD.search(u.source.text) or _HARD.search(u.clause)]


def _pace(units: list[Unit], first_days: list[date]) -> tuple[str, Unit] | None:
    """The insight: most of the notes in one busy stretch, then quiet."""
    n = len(units)
    if n < 6:
        return None
    window = max(range(n), key=lambda i: (sum(1 for d in first_days if 0 <= _gap(first_days[i], d) <= 30), -i))
    inside = [k for k, d in enumerate(first_days) if 0 <= _gap(first_days[window], d) <= 30]
    if len(inside) * 2 < n or len(inside) == n:
        return None
    last = inside[-1]
    end = first_days[last]
    where = f"in {_part(first_days[window])}{_month(first_days[window])}" if (first_days[window].year, first_days[window].month) == (end.year, end.month) else (
        f"between {_part(first_days[window])}{_month(first_days[window])} and {_part(end)}{_month(end)}")
    text = f"{_NUMBERS.get(len(inside), len(inside)).capitalize()} of the {_NUMBERS.get(n, n)} fall {where}; after that you wrote far less often."
    return text, units[last]


def story(out, count: str, units: list[Unit], days: list[date], topic: str, p: Plan) -> None:  # noqa: ANN001
    """Fill `out.lines` and `out.rows` from the units, oldest first; the pace
    insight waits in `out.spare` for `_finish`, which says it only when no
    other rule found an insight."""
    said: list[str] = []
    lead_unit = next((u for u in units if _SEMESTER.search(u.source.text)), units[0])
    span = span_words(p.first, p.last)
    lead = f"You have {count} about {topic}, and they follow {p.arc}, {span}." if p.arc == "one semester" else f"You have {count} about {topic}, written from {span}."
    out.lines.append(lead)
    out.rows.append(_row(lead_unit, lead))
    for n, run in enumerate(p.chunks):
        sentences, prev = [], None
        for k, i in enumerate(run):
            unit = units[i]
            opener = _when(prev, days[i], said, k == 0)
            said.append(opener)
            text = sentence(unit, opener)
            sentences.append(text)
            out.rows.append(_row(unit, text))
            prev = days[i]
        hard = _hard_run([units[i] for i in run])
        if len(hard) >= 2:
            note = "That reads like a hard stretch."
            sentences.append(note)
            out.rows.append(_row(hard[0], note))
        elif n == len(p.chunks) - 1 and _FINISH.search(units[run[-1]].source.text):
            note = "Congratulations on getting it done."
            sentences.append(note)
            out.rows.append(_row(units[run[-1]], note))
        out.lines.append(" ".join(sentences))
    found = _pace(units, days)
    if found:
        out.spare = (found[0], _row(found[1], found[0]))
