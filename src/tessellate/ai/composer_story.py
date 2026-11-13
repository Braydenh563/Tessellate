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

from tessellate.ai import composer_frame

#: Two notes are a pair, said in the question's own shape; from three a stretch
#: is written as one. Up to MAX_NOTES the paragraphs are cut at the biggest
#: gaps; past it a paragraph holds at most PARAGRAPH_NOTES, a sentence at most
#: SENTENCE_NOTES (notes of one theme told together), and WOVEN_LIMIT notes
#: are the most told (past that the old list answers, never a half story).
MIN_NOTES = 3
MAX_NOTES = 14
MAX_PARAGRAPHS = 3
PARAGRAPH_NOTES = 8
#: Under this many, the woven answer is for notes a frame would group (the digest decides).
PLAIN_NOTES = 5
SENTENCE_NOTES = 3
WOVEN_LIMIT = 40
_MIN_RUN = 3
_NUMBERS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen"}
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
#: A quote that says "today" (or yesterday, tonight) means the day it was written, not the day it is read.
_QUOTED_RELATIVE = re.compile(r"“[^”]*\b(?:today|tonight|yesterday|tomorrow|this (?:morning|afternoon|evening)|last night)\b[^”]*”", re.I)
_REPORT = re.compile(r"^you (?:mentioned|said|noted|recorded|put down|jotted down) that ", re.I)
#: "This note pulls together ..." (L-chat-39): the note's own subject is its title.
_THIS_NOTE = re.compile(r"^(?:this|the) note\s+(?=[a-z])", re.I)
#: The digest's provenance tail: the story cites the note instead.
_FROM_NOTE = re.compile(r",? from your [^,.]{1,60} note$")
#: "your uni days ... are Tuesday": the person's own line in the present ("My uni days ..."), under a
#: time opener, is what was noted then; "your Guide is in four phases" describes the note and stays.
_PRESENT = re.compile(r"^your\b(?:\s+[^\s,.]+){0,8}?\s+(?:are|is)\b", re.I)
#: Typed without its apostrophe: said back flat ("You didnt lock in") it reads as the app's typo, so it is quoted.
_RAW = re.compile(r"\b(?:didnt|dont|cant|wont|couldnt|wouldnt|isnt|im|ive)\b", re.I)
_DEFINES = re.compile(r"^(?P<term>[^.]{2,60}?) (?:is|are|means|refers to) (?P<what>(?:the|a|an|when|how|any)\b.+)$", re.I | re.S)
_ASIDE = re.compile(r"\s*[\u2013\u2014-]\s[^\u2013\u2014]*?\s[\u2013\u2014-]\s*")


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
    biggest gaps, keeping the runs about even (a run of one note is a line).
    Past MAX_NOTES a paragraph holds PARAGRAPH_NOTES at most (`_capped`)."""
    n = len(days)
    if n > MAX_NOTES:
        return _capped(days)
    if n < 5:
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


def _capped(days: list[date]) -> list[list[int]]:
    """Many notes: cuts at the biggest gaps first (each run keeping _MIN_RUN),
    then any run still over PARAGRAPH_NOTES halved at its biggest inner gap."""
    n = len(days)
    cuts: list[int] = []
    for c in sorted(range(_MIN_RUN, n - _MIN_RUN + 1), key=lambda c: -_gap(days[c - 1], days[c])):
        if len(cuts) + 1 >= -(-n // PARAGRAPH_NOTES):
            break
        if all(abs(c - o) >= _MIN_RUN for o in cuts):
            cuts.append(c)
    runs = [[a, b] for a, b in itertools.pairwise([0, *sorted(cuts), n])]
    while (long := next((r for r in runs if r[1] - r[0] > PARAGRAPH_NOTES), None)) is not None:
        inner = range(long[0] + _MIN_RUN, long[1] - _MIN_RUN + 1)
        at = max(inner, key=lambda c: (_gap(days[c - 1], days[c]), -abs(c - (long[0] + long[1]) // 2)))
        runs[runs.index(long): runs.index(long) + 1] = [[long[0], at], [at, long[1]]]
    return [list(range(a, b)) for a, b in runs]


def _arc(days: list[date], texts: list[str]) -> str:
    months = (days[-1].year - days[0].year) * 12 + days[-1].month - days[0].month
    if any(_SEMESTER.search(t) for t in texts) and 2 <= months <= 6:
        return "one semester"
    return {0: "", 1: "a month or so"}.get(months, f"about {months} months") if months > 0 else ""


def plan(days: list[date], texts: list[str]) -> Plan | None:
    """The plan for notes written on `days` (oldest first), or None when there
    are too few or too many to weave."""
    if not (MIN_NOTES <= len(days) <= WOVEN_LIMIT):
        return None
    return Plan(days[0], days[-1], _chunks(days), _arc(days, texts))


def _month(d: date) -> str:
    return _MONTHS[d.month - 1]


def _part(d: date) -> str:
    return "early " if d.day <= 10 else "mid " if d.day <= 20 else "late "


def span_words(first: date, last: date) -> str:
    """"July to early November": the months, with a part of the last one."""
    if (first.year, first.month) == (last.year, last.month):
        return _month(first) if _part(first) != _part(last) else f"{_part(first)}{_month(first)}"
    year = f" {last.year}" if first.year != last.year else ""
    return f"{_month(first)} to {_part(last)}{_month(last)}{year}"


# --- the sentences ---------------------------------------------------------------


def _lower(clause: str) -> str:
    return clause if re.match(r"I\b|[A-Z]{2,}", clause) else clause[:1].lower() + clause[1:]


def clipped(quote: str, limit: int = 12) -> str:
    """A long quote cut to its first six words and an ellipsis, so a quoted line stays a clause.
    A line quoted whole keeps its two sentences up to `limit` words (R3-11)."""
    words = quote.split()
    return quote if len(words) <= limit else " ".join(words[:6]).rstrip(",;:") + "…"


def _short_quotes(body: str) -> str:
    """Each quote in `body` cut like any other quote (`_clipped`): a filler note's whole run-on was quoted (audit 1031 C5)."""
    return re.sub(r"“([^”]*)”", lambda m: f"“{clipped(m.group(1))}”", body)


def _clean_quote(text: str) -> str:
    """A note's words for a quote: no emoji, no hashtags, no trailing marks."""
    text = re.sub(r"(?:^|\s)[:;]-?[dDpP)(]+(?=\s|$)", "", _EMOJI.sub("", text))
    #: A hashtag is filing, not something the person said (the plain lines drop it the same way).
    #: Word by word, not one trailing-run regex (CodeQL 2192: `(\s*#tag)+\s*$` is polynomial on tabs).
    words = text.split()
    while words and re.fullmatch(r"#[A-Za-z][\w-]*", words[-1]):
        words.pop()
    text = " ".join(words)
    text = re.sub(r"(?<![\w&/])#([A-Za-z][\w-]*)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip().rstrip("!.?:").strip()


def quoted_if_slang(text: str) -> str:
    """`text` as the person typed it, in quotes, when it is slang or an apostrophe-less contraction
    (a volunteered insight says it as the story does, never as the app's own voice)."""
    quote = _clean_quote(text)
    return f"“{quote}”" if _said_raw(text, quote) else text


def _caps_days(text: str) -> str:
    return _WEEKDAY.sub(lambda m: m.group(0).capitalize(), text)


@dataclass
class Unit:
    """One sentence of the story: its words and the note sentence it cites."""

    view: object
    clause: str  # begins with "you" or "your", no time lead, no stop
    source: object  # the composer_read.Sentence cited
    row: dict | None = None


def _defined(view, first, title: str) -> Unit | None:  # noqa: ANN001
    """A note that says what its title is: "your X note defines the term as ..."."""
    said = _DEFINES.match(_ASIDE.sub(" ", first.text).strip().rstrip("."))
    if not (title and said) or re.match(r"(?:i|my|you|we)\b", first.text, re.I) or title.lower().split()[0] not in said.group("term").lower():
        return None
    return Unit(view, f"your {title} note defines the term as {_lower(said.group('what')).strip()}", first)


def _clause(line: str, title: str, quote: str) -> str:
    """The told line as a clause beginning "you" or "your", with no time lead and
    one sentence; a line with no such start (or "that uni is done") is quoted."""
    body = _LEAD.sub("", line.strip()).rstrip(".")
    reported = _REPORT.match(body)
    if reported:
        #: "You mentioned that you ..." keeps its clause; "that uni is done" has no "you" to lead and is quoted.
        body = body[reported.end():] if re.match(r"you\b", body[reported.end():], re.I) else "-"
    #: One sentence a unit: the claim is the first, and a second would be uncited.
    body = _FROM_NOTE.sub("", re.split(r"(?<=[a-z0-9])\.\s+(?=[A-Z])", body, maxsplit=1)[0])
    if title and (this := _THIS_NOTE.match(body)):
        return _caps_days(f"your “{_clean_quote(title)}” note {_short_quotes(body[this.end():])}")
    if _PRESENT.match(body) and re.match(r"(?:my|i)\b", quote, re.I):
        return _caps_days(f"you noted that {_lower(_short_quotes(body))}")
    if re.match(r"(?:you|your)\b", body, re.I):
        return _caps_days(_lower(_short_quotes(body)))
    said = _clean_quote(title) if title and len(title.split()) <= 6 else clipped(quote)
    return f"you wrote “{said}”"


def _first(view):  # noqa: ANN001, ANN202
    """The sentence a note opens on: its first prose, else its first unit."""
    prose = [s for s in view.sentences if s.kind == "prose"]
    return (prose or view.sentences or [None])[0]


def _said_raw(text: str, quote: str) -> bool:
    """Slang or an apostrophe-less contraction in a short sentence: quoted, never re-voiced."""
    return bool(_SLANG.search(text) or _RAW.search(text)) and 0 < len(quote.split()) <= 14


def clause_of(view, line: str, row: dict | None) -> Unit | None:  # noqa: ANN001
    """The note as a clause: a definition says it defines, slang is quoted,
    an ordinary line loses its time lead and its "you mentioned that".
    None when a quote would carry a "today" the story cannot pin to its day:
    the plain lines say it against the day it was written."""
    unit = _clause_of(view, line, row)
    if unit is not None and _QUOTED_RELATIVE.search(unit.clause):
        return None
    return unit


def _clause_of(view, line: str, row: dict | None) -> Unit | None:  # noqa: ANN001
    first = _first(view)
    if first is None:
        return None
    title = (view.title or "").strip().rstrip("…").strip() if view.titled else ""
    quote = _clean_quote(first.text)
    if defined := _defined(view, first, title):
        return defined
    if _said_raw(first.text, quote):
        return Unit(view, f"you wrote “{clipped(quote)}”", first)
    source = next((s for s in view.sentences if row and s.start == row.get("start")), first)
    return Unit(view, _clause(line, title, quote), source, row) if line else None


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
    text = f"{str(_NUMBERS.get(len(inside), len(inside))).capitalize()} of the {_NUMBERS.get(n, n)} fall {where}; after that you wrote far less often."
    return text, units[last]


def _beats(run: list[int], themes: list[list[int]]) -> list[list[int]]:
    """A paragraph's notes as sentences: notes of one theme (a shared tag or a link) told together,
    at most SENTENCE_NOTES to a sentence, the rest in time order. A theme the paragraph holds one
    of is no theme here."""
    seat = {i: t for t, held in enumerate(themes) for i in held}
    beats: list[list[int]] = []
    for i in run:
        together = i in seat and sum(1 for j in run if seat.get(j) == seat[i]) > 1
        placed = next((b for b in beats if together and seat.get(b[0]) == seat[i] and len(b) < SENTENCE_NOTES), None)
        if placed is not None:
            placed.append(i)
        else:
            beats.append([i])
    return beats


def _later(clause: str, before: str) -> str:
    """A clause after another in one sentence drops its "you" when the one before also began with it."""
    return re.sub(r"^you ", "", clause) if before.startswith("you ") else clause


def _joined(units: list[Unit]) -> str:
    """Several clauses in one sentence."""
    parts = [units[0].clause]
    for u in units[1:]:
        parts.append(_later(u.clause, units[len(parts) - 1].clause))
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def _beat(out, group: list[Unit], opener: str) -> str:  # noqa: ANN001
    """One sentence for one theme's notes (or one note), each cited by its own clause."""
    body = _joined(group)
    text = f"{opener}, {body}." if opener else f"{body[:1].upper()}{body[1:]}."
    if len(group) == 1:
        out.rows.append(_row(group[0], text))
        return text
    for k, unit in enumerate(group):
        out.rows.append(_row(unit, unit.clause if k == 0 else _later(unit.clause, group[k - 1].clause)))
    return text


def _lead_line(count: str, topic: str, p: Plan) -> str:
    """The opening sentence: the count, the topic, and the span (or the one semester they follow)."""
    span = span_words(p.first, p.last)
    if p.arc == "one semester":
        return f"You have {count} about {topic}, and they follow {p.arc}, {span}."
    return f"You have {count} about {topic}, written from {span}." if " to " in span else f"You have {count} about {topic}, all written in {span}."


def _tell_run(out, run: list[int], last: bool, units: list[Unit], days: list[date], said: list[str], themes: list[list[int]]) -> str:  # noqa: ANN001
    """One stretch as a paragraph: a sentence a beat, then the hard-stretch or finished note when it applies."""
    sentences, prev = [], None
    for k, beat in enumerate(_beats(run, themes)):
        opener = _when(prev, days[beat[0]], said, k == 0)
        said.append(opener)
        sentences.append(_beat(out, [units[i] for i in beat], opener))
        prev = days[beat[-1]]
    hard = _hard_run([units[i] for i in run])
    if len(hard) >= 2:
        note = "That reads like a hard stretch."
        sentences.append(note)
        out.rows.append(_row(hard[0], note))
    elif last and _FINISH.search(units[run[-1]].source.text):
        note = "Congratulations on getting it done."
        sentences.append(note)
        out.rows.append(_row(units[run[-1]], note))
    return " ".join(sentences)


def story(out, count: str, units: list[Unit], days: list[date], topic: str, p: Plan, themes: list[list[int]] | None = None, first: tuple | None = None) -> None:  # noqa: ANN001
    """Fill `out.lines` and `out.rows` from the units, oldest first; the pace
    insight waits in `out.spare` for `_finish`, which says it only when no
    other rule found an insight. `themes` are the unit indexes that go together."""
    said: list[str] = []
    lead_unit = next((u for u in units if _SEMESTER.search(u.source.text)), units[0])
    lead = _lead_line(count, topic, p)
    out.lines.append(lead)
    out.rows.append(_row(lead_unit, lead))
    if first and first[0] is not None:
        #: The best-ranked note of a crowded notebook, told on its own ahead of the stretches (audit 1031 C4).
        said.append(_when(None, first[1], said, True))
        out.lines.append(_beat(out, [first[0]], said[-1]))
    for n, run in enumerate(p.chunks):
        out.lines.append(_tell_run(out, run, n == len(p.chunks) - 1, units, days, said, themes or []))
    found = _pace(units, days)
    if found:
        out.spare = (found[0], _row(found[1], found[0]))


def plan_of(members, lead):  # noqa: ANN001
    """The dated notes (lead apart) and their plan, or None when the notes do not fit the story shape."""
    #: Past MAX_NOTES the best-ranked note (the defining one leads `members`) is told first, on its own; the rest
    #: follow oldest first (audit 1031 C4: filler with the word repeated is not what the story opens with).
    dated = sorted((v for v in members if v.written and v is not lead), key=lambda v: (v.written, v.id))
    made = plan([v.written for v in dated], [v.note.get("content") or "" for v in dated]) if len(dated) == len(members) - (lead is not None) else None
    #: Under five notes the plain lines have no filler to lose; they are woven only when a frame would have
    #: told some of them as "More loosely related" or "More from X" (INBOX 1743 follow-up).
    if made is None or (len(dated) < PLAIN_NOTES and not _would_fill(dated)):
        return None
    if lead is not None and lead.written:
        #: The span says all the notes' days, the lead's too.
        made.first, made.last = min(made.first, lead.written), max(made.last, lead.written)
    return dated, made


def _would_fill(dated) -> bool:  # noqa: ANN001
    """Whether the frame would tell any of these notes as "more loosely related": the filler a story replaces."""
    return any(g.band == "loose" for g in composer_frame.groups([v.note for v in dated]))


def themed(dated) -> list[list[int]]:  # noqa: ANN001
    """The positions (oldest first) of the notes that go together, by a tag they share or a link, one list a theme."""
    place = {v.id: i for i, v in enumerate(dated)}
    return [sorted(place[i] for i in g.ids) for g in composer_frame.themes([v.note for v in dated]) if len(g.ids) > 1]
