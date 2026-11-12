"""The learned store audits itself (CHAT_PLAN decision 68, with 67's context rule).

"Check what it learned" re-reads every open claim, question and pair the night
shift stored against its note as the note reads now, and says for each row
that no longer holds why: retire it (certain: the note is gone or no longer
says it, the person marked those words wrong, the note is a joke or a quote)
or flag it (a judgement: it disagrees with a newer note, a date it speaks of
as ahead has passed, the same words came from another note).

Pure on purpose. `check` takes plain views of the rows and notes, the
verdicts (`ai/verdicts.Known`) and the day, and returns findings; the rows
are read and written by `ai/learned_audit_run.py`, so every rule here is
tested with no database and a fixed day (CLAUDE.md section 5: tests use a
fixed clock).

Only what a rule wrote is judged: a row the person edited, and their own
"wrong" and "pinned" rows, are never retired or flagged here (decision 67:
their word is the last word).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from tessellate.ai import facts
from tessellate.ai.verdicts import Known, norm

RETIRE = "retire"
FLAG = "flag"

#: Tags that mark a note as not the person's own claims (decision 67).

#: A date this many days gone, spoken of as ahead, is stale.
STALE_DAYS = 30

#: Most pairs of claims compared for a contradiction in one check, so a big
#: notebook costs a bounded amount.
MAX_COMPARES = 4000
#: A shared word in more rows than this says nothing about what a row is about.
COMMON_WORD_ROWS = 40

_WORDS_AHEAD = frozenset({
    "will", "going", "upcoming", "next", "due", "deadline", "scheduled", "tomorrow", "soon",
    "until", "expires", "expected", "planning", "plan", "plans", "coming",
})
_MONTHS = {
    name: number
    for number, names in enumerate(
        ("jan january", "feb february", "mar march", "apr april", "may", "jun june", "jul july",
         "aug august", "sep sept september", "oct october", "nov november", "dec december"),
        start=1,
    )
    for name in names.split()
}
_MONTH_NAMES = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH_YEAR = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_NAMES})\.?,?\s+(\d{{4}})\b", re.I)
_MONTH_DAY_YEAR = re.compile(rf"\b({_MONTH_NAMES})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I)


@dataclass(frozen=True)
class FactView:
    """One stored row, as the audit reads it."""

    id: int
    entry_id: int
    kind: str
    text: str
    span: tuple[int, int] = (0, 0)
    edited: bool = False
    written: datetime | None = None
    #: A pair row's two sides (`fact_id`, `other_fact_id`); empty otherwise.
    sides: tuple[int, ...] = ()


@dataclass(frozen=True)
class NoteView:
    """One note, as it reads now. A deleted or unreadable note is `gone`."""

    id: int
    content: str = ""
    tags: tuple[str, ...] = ()
    written: datetime | None = None
    gone: bool = False


@dataclass(frozen=True)
class Finding:
    fact_id: int
    action: str
    code: str
    reason: str
    #: What the finding is about, for the row's line (the other note's words, a date).
    detail: str = ""


@dataclass
class _Judged:
    """What `check` has decided so far."""

    found: dict[int, Finding] = field(default_factory=dict)

    def add(self, fact: FactView, action: str, code: str, reason: str, detail: str = "") -> bool:
        if fact.id in self.found:
            return False
        self.found[fact.id] = Finding(fact.id, action, code, reason, detail)
        return True


def context_reason(fact: FactView, note: NoteView) -> str | None:
    """Why this sentence is not a claim about the person, or None (decision 67);
    the rule is `facts.context_reason`, which the night shift reads before it
    proposes a sentence at all."""
    return facts.context_reason(fact.text, fact.span, note.content, note.tags)


def _note_check(judged: _Judged, fact: FactView, note: NoteView | None, known: Known) -> None:
    """The checks that read one row against its note."""
    if note is None or note.gone:
        judged.add(fact, RETIRE, "note-gone", "The note it came from is gone.")
    elif norm(fact.text) not in norm(note.content):
        judged.add(fact, RETIRE, "note-edited", "The note no longer says this.")
    elif known.is_wrong(fact.entry_id, fact.text):
        judged.add(fact, RETIRE, "marked-wrong", "You marked this sentence wrong.")
    elif any(norm(fact.text) == sentence for _note, sentence in known.wrong):
        judged.add(fact, RETIRE, "marked-wrong", "The same words are a sentence you marked wrong.")
    else:
        why = context_reason(fact, note)
        if why:
            judged.add(fact, RETIRE, "out-of-context", why)


def _duplicates(judged: _Judged, rows: list[FactView]) -> None:
    """The first of rows with the same words is kept. A repeat in the same
    note is retired; one from another note is flagged (two notes can both say
    it, and it stays until the person decides)."""
    first: dict[tuple[str, str], FactView] = {}
    for fact in sorted(rows, key=lambda row: row.id):
        if fact.id in judged.found:
            continue
        key = (fact.kind, norm(fact.text))
        kept = first.setdefault(key, fact)
        if kept is fact:
            continue
        if kept.entry_id == fact.entry_id:
            judged.add(fact, RETIRE, "duplicate", "The same sentence is already learned from this note.")
        else:
            judged.add(fact, FLAG, "duplicate", "Another note says the same.", detail=f"note {kept.entry_id}")


def _later(a: FactView, b: FactView, notes: dict[int, NoteView]) -> bool:
    """Whether `a` was written after `b`: by the note's own day, else the row's."""
    day_a, day_b = (notes[a.entry_id].written if a.entry_id in notes else None), (notes[b.entry_id].written if b.entry_id in notes else None)
    if day_a and day_b and day_a != day_b:
        return day_a > day_b
    return a.id > b.id


def _contradictions(judged: _Judged, rows: list[FactView], notes: dict[int, NoteView]) -> None:
    """The older of two claims that differ in a number or a not is flagged
    (`facts._local_disagreement`, the one disagreement no model is needed for)."""
    claims = [row for row in rows if row.kind == "claim" and row.id not in judged.found]
    by_word: dict[str, list[FactView]] = {}
    for claim in claims:
        for word in facts._terms(claim.text):
            by_word.setdefault(word, []).append(claim)
    seen: set[tuple[int, int]] = set()
    for group in by_word.values():
        if len(group) > COMMON_WORD_ROWS:
            continue
        for index, a in enumerate(group):
            for b in group[index + 1:]:
                pair = (min(a.id, b.id), max(a.id, b.id))
                if pair in seen or a.entry_id == b.entry_id:
                    continue
                seen.add(pair)
                if len(seen) > MAX_COMPARES:
                    return
                why = facts._local_disagreement(a.text, b.text)
                if why:
                    older, newer = (b, a) if _later(a, b, notes) else (a, b)
                    judged.add(older, FLAG, "contradiction", f"A newer note says otherwise. {why}", detail=newer.text)


def _dates_in(text: str) -> list[date]:
    found = [_make_date(m.group(1), m.group(2), m.group(3)) for m in _ISO_DATE.finditer(text)]
    found += [_make_date(m.group(3), _MONTHS[m.group(2).lower()], m.group(1)) for m in _DAY_MONTH_YEAR.finditer(text)]
    found += [_make_date(m.group(3), _MONTHS[m.group(1).lower()], m.group(2)) for m in _MONTH_DAY_YEAR.finditer(text)]
    return [day for day in found if day is not None]


def _make_date(year, month, day) -> date | None:  # noqa: ANN001
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def stale_date(text: str, today: date) -> date | None:
    """A date in `text` more than `STALE_DAYS` before `today`, when the
    sentence speaks of it as still ahead ("due", "will", "next"...)."""
    words = {word.lower() for word in re.findall(r"[A-Za-z']+", text)}
    if not words & _WORDS_AHEAD:
        return None
    gone = [day for day in _dates_in(text) if day < today - timedelta(days=STALE_DAYS)]
    return max(gone) if gone else None


def _stale(judged: _Judged, rows: list[FactView], today: date) -> None:
    for fact in rows:
        if fact.kind in ("claim", "question") and fact.id not in judged.found:
            day = stale_date(fact.text, today)
            if day:
                judged.add(fact, FLAG, "stale-date", f"It speaks of {day.day} {day.strftime('%B')} {day.year} as ahead, and that has passed.", detail=day.isoformat())


def _pairs(judged: _Judged, rows: list[FactView]) -> None:
    """A tension or an answer is retired when a side of it was (or is gone)."""
    gone = {fid for fid, item in judged.found.items() if item.action == RETIRE}
    open_ids = {row.id for row in rows if row.kind not in facts.PAIR_KINDS and row.id not in gone}
    for fact in rows:
        if fact.kind in facts.PAIR_KINDS and fact.sides and not set(fact.sides) <= open_ids:
            judged.add(fact, RETIRE, "pair-side-gone", "One of the two sentences it set side by side is no longer learned.")


def check(rows: Iterable[FactView], notes: dict[int, NoteView], known: Known, today: date) -> list[Finding]:
    """What no longer holds. `rows` are the open claims, questions and pairs;
    `notes` the notes they came from as they read now. The rows a person
    wrote or edited are not judged. Retirements first, then flags."""
    judged = _Judged()
    rows = [row for row in rows if not row.edited and row.kind in facts.JUDGED_KINDS]
    for fact in rows:
        if fact.kind not in facts.PAIR_KINDS:
            _note_check(judged, fact, notes.get(fact.entry_id), known)
    _duplicates(judged, [row for row in rows if row.kind not in facts.PAIR_KINDS])
    _pairs(judged, rows)
    _contradictions(judged, rows, notes)
    _stale(judged, rows, today)
    return sorted(judged.found.values(), key=lambda item: (item.action != RETIRE, item.fact_id))
