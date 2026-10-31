"""Which of the notes is cheaper, sooner, older (audit 1030 Z58, composer-1031).

A comparison that asks for a figure or a day leads with the figures or days:
"**Lisbon trip** is cheaper: $420 against $3,000 for **Tokyo trip**." The same
for "which trip is sooner" with no sides named (every note about trips with a
day ahead) and "which note is the oldest about baking" (the notes' own days).
One table of the words (`_RELATIONS`) says what each word ranks by and how it
is said; a word is never a branch of its own.

The composer calls `two` for a comparison and `which_one` for a question that
names no sides; both write the lead into the answer and return whether they
did, so the ordinary answer follows when the notes hold no figure or day to
rank by. Nothing here imports the composer at load (it imports this).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

#: What each comparison word ranks by (`by`), which end wins (`low`: the least
#: is first), and the template key that says it. "age" ranks by the day a note
#: was written, "ahead" by the days a note names that are still to come, and
#: "money" by the figures it holds.
_RELATIONS: dict[str, tuple[str, bool, str]] = {
    "cheaper": ("money", True, "is_cheaper"),
    "cheapest": ("money", True, "is_cheaper"),
    "more expensive": ("money", False, "costs_more"),
    "less expensive": ("money", True, "is_cheaper"),
    "pricier": ("money", False, "costs_more"),
    "costlier": ("money", False, "costs_more"),
    "dearer": ("money", False, "costs_more"),
    "sooner": ("ahead", True, "comes_first"),
    "soonest": ("ahead", True, "comes_first"),
    "next": ("ahead", True, "comes_first"),
    "earlier": ("ahead", True, "comes_first"),
    "nearer": ("ahead", True, "comes_first"),
    "closer": ("ahead", True, "comes_first"),
    "later": ("ahead", False, "comes_later"),
    "further away": ("ahead", False, "comes_later"),
    "farther away": ("ahead", False, "comes_later"),
    "older": ("age", True, "is_older"),
    "oldest": ("age", True, "is_oldest"),
    "newer": ("age", False, "is_newer"),
    "newest": ("age", False, "is_newest"),
    "more recent": ("age", False, "is_newer"),
    "most recent": ("age", False, "is_newest"),
}
#: Said of notes, these rank by the day written, not by a day ahead.
_NOTE_AGE = {"earliest": "oldest", "latest": "newest", "first": "oldest", "last": "newest"}
_WORD = "|".join(sorted((*_RELATIONS, *_NOTE_AGE), key=len, reverse=True))
_WHICH = re.compile(
    rf"^which\s+(?:(?P<a>(?!(?:is|are|was|were|comes?)\b)[\w'-]+(?:\s(?!(?:is|are|was|were|comes?)\b)[\w'-]+){{0,2}})\s+)?"
    rf"(?:is|are|was|were|comes?)\s+(?:(?:written|made|saved|created|added|started)\s+)?(?:the\s+)?(?P<rel>{_WORD})(?:\s+(?P<b>(?!(?:about|on|for|regarding|with|in|of)\b)[\w'-]+(?:\s(?!(?:about|on|for|regarding|with|in|of)\b)[\w'-]+){{0,2}}?))?"
    r"(?:\s+(?:about|on|for|regarding|with|in|of)\s+(?:my\s+|the\s+)?(?P<topic>[\w'-]+(?:\s[\w'-]+){0,3}))?\W*$",
    re.I,
)
#: "What is my newest baking note", "what's the oldest note about baking".
_PREP = r"(?:about|on|for|regarding|with|in|of)"
_WHAT = re.compile(
    rf"^what(?:'s|\s+is|\s+was)\s+(?:my\s+|the\s+)?(?P<rel>{_WORD})(?:\s+(?P<b>(?!{_PREP}\b)[\w'-]+(?:\s(?!{_PREP}\b)[\w'-]+){{0,2}}?))?"
    rf"(?:\s+{_PREP}\s+(?:my\s+|the\s+)?(?P<topic>[\w'-]+(?:\s[\w'-]+){{0,3}}))?\W*$",
    re.I,
)
_NOT_SUBJECT = frozenset({"note", "notes", "entry", "entries", "one", "ones", "thing", "things", "my", "the", "of", "a", "an"})
#: The figure a sentence leads with when it names a cost.
_COST_CUE = re.compile(r"\b(?:cost|costs|budget|price|priced|total|paid|pay|fee|fees|worth)\b", re.I)
#: A figure is only ranked against one in the same money.
#: What each template key says; the composer's `PHRASES` take these, and the
#: digest's one-line form (`line`) says the same words.
SAID = {
    "is_cheaper": " is cheaper: ",
    "costs_more": " costs more: ",
    "comes_first": " comes first: ",
    "comes_later": " comes later: ",
    "is_older": " is older: ",
    "is_oldest": " is the oldest: ",
    "is_newer": " is newer: ",
    "is_newest": " is the newest: ",
    "figure_against": " against ",
    "figure_for": " for ",
}
_SHOWN_AS = {"USD": "$", "EUR": "€", "GBP": "£"}


def relation(word: str, note_noun: bool) -> tuple[str, bool, str] | None:
    """How `word` ranks: ("money" | "ahead" | "age", least first, template)."""
    low = " ".join((word or "").lower().split())
    if low in _NOTE_AGE and note_noun:
        low = _NOTE_AGE[low]
    elif low in ("earliest", "first"):
        low = "sooner"
    elif low in ("latest", "last"):
        low = "later"
    return _RELATIONS.get(low)


def _facts(view):  # noqa: ANN001, ANN202
    from tessellate.ai import factgraph

    note = view.note
    if view.written and not note.get("created_at"):
        note = {**note, "created_at": view.written.isoformat()}
    return note, factgraph.facts(note)


def figure_of(view, shared: str | None = None):  # noqa: ANN001, ANN202
    """`(amount, shown text, money)` of the figure a note leads with: one in
    a sentence that names a cost, else its first. `shared` is the money the
    other side's figure is in; a figure in another money is left out."""
    note, facts = _facts(view)
    content = str(note.get("content") or "")
    found = []
    for fact in facts:
        if fact.kind != "money" or fact.attrs.get("currency") not in _SHOWN_AS:
            continue
        if shared and fact.attrs["currency"] != shared:
            continue
        start = max(content.rfind(mark, 0, fact.start) for mark in (". ", "\n")) + 1
        cued = bool(_COST_CUE.search(content[start: fact.end]))
        found.append((not cued, fact.start, float(fact.attrs["value"]), fact.text, fact.attrs["currency"]))
    if not found:
        return None
    _, at, amount, text, money = min(found)
    return amount, text, money, at


def dates_of(view, today: date) -> list[tuple[date, str, int]]:  # noqa: ANN001
    """The days a note names that are still to come, each with how it is said
    ("14 November", "April 2027"); a day told as past is not one."""
    from tessellate.ai import composer, recognise

    note, facts = _facts(view)
    content = str(note.get("content") or "")
    days = []
    for fact in facts:
        if fact.kind != "date" or not fact.when or recognise.told_as_past(_sentence(content, fact.start)):
            continue
        grain = fact.when[2]
        day = composer._fact_day(fact, today, "future") if grain == "day" else fact.when[0]  # noqa: SLF001
        if (fact.when[1] if grain != "day" else day) >= today:
            days.append((day, _said_day(day, grain, today), fact.start))
    return sorted(days)


def _sentence(content: str, at: int) -> str:
    start = max(content.rfind(mark, 0, at) for mark in (". ", "! ", "? ", "\n")) + 1
    stops = [i for i in (content.find(mark, at) for mark in (". ", "! ", "? ", "\n")) if i >= 0]
    return content[start: min(stops) if stops else len(content)]


_MONTHS = "January February March April May June July August September October November December".split()


def _said_day(day: date, grain: str, today: date) -> str:
    if grain == "month":
        return f"{_MONTHS[day.month - 1]} {day.year}" if day.year != today.year else _MONTHS[day.month - 1]
    return f"{day.day} {_MONTHS[day.month - 1]}" + ("" if day.year == today.year else f" {day.year}")


def written_of(view, today: date):  # noqa: ANN001, ANN202
    return (view.written, _said_day(view.written, "day", today), None) if view.written else None


@dataclass
class Row:
    """A note, what it is ranked by, how that is said, and where in the note
    the figure or day is written (None for the day the note was written)."""

    view: object
    key: object
    shown: str
    at: int | None
    money: str = ""


@dataclass
class Versus:
    """The winner first, with the template key that says what it is."""

    key: str
    rows: list[Row]


def _row(kind: str, view, today: date, low: bool, shared: str):  # noqa: ANN001, ANN202
    if kind == "money":
        got = figure_of(view, shared or None)
        return got and Row(view, got[0], got[1], got[3], got[2])
    if kind == "ahead":
        days = dates_of(view, today)
        pick = days and days[0 if low else -1]
        return pick and Row(view, pick[0], pick[1], pick[2])
    got = written_of(view, today)
    return got and Row(view, got[0], got[1], got[2])


def _ranked(kind: str, notes: list, today: date, low: bool) -> list[Row]:  # noqa: ANN001
    """The notes that have a figure or a day to rank by, best first; the day
    ahead is each note's nearest (its latest, for a word that asks for the
    later one), and every figure is in the first one's money."""
    rows: list[Row] = []
    for view in notes:
        row = _row(kind, view, today, low, rows[0].money if rows else "")
        if row:
            rows.append(row)
    return sorted(rows, key=lambda r: (r.key, r.view.rank), reverse=not low)


def _versus(key: str, rows: list[Row]) -> Versus | None:
    """None when fewer than two notes are ranked or the first two tie."""
    return Versus(key, rows) if len(rows) >= 2 and rows[0].key != rows[1].key else None


def _asked_word(question: str) -> str:
    found = re.search(rf"\b({_WORD})\b", question or "", re.I)
    return found.group(1).lower() if found else ""


def two(question: str, sides: list[list], today: date) -> Versus | None:
    """"Which is cheaper, Lisbon or Tokyo": the note each side names, ranked
    by the word the question asks with; None when it asks for none or a side
    holds nothing to rank by."""
    word = _asked_word(question)
    rel = relation(word, False) if word else None
    if rel is None or any(not side for side in sides):
        return None
    kind, low, key = rel
    rows: list[Row] = []
    for side in sides:
        got = [r for r in _ranked(kind, side, today, low) if not rows or not r.money or r.money == rows[0].money]
        if not got:
            return None
        rows.append(got[0])
    rows.sort(key=lambda r: (r.key, r.view.rank), reverse=not low)
    return _versus(key, rows)


def _read_which(question: str):  # noqa: ANN202
    """`(subject words, relation)` of a "which ... is sooner" question, or
    None when it is not one or names nothing to rank."""
    text = " ".join((question or "").split())
    found = _WHICH.match(text) or _WHAT.match(text)
    if not found:
        return None
    named = found.groupdict()
    nouns = [w for part in (named.get("a"), named.get("b"), named.get("topic")) for w in (part or "").lower().split()]
    note_noun = any(w in ("note", "notes", "entry", "entries") for w in nouns)
    #: "what is the latest on the sync rewrite" asks for the news, not for a
    #: ranking: a "what is the newest ..." ranks only when it names a note.
    if found.re is _WHAT and not note_noun:
        return None
    rel = relation(found.group("rel"), note_noun or not named.get("a"))
    subject = [w for w in nouns if w not in _NOT_SUBJECT]
    return (subject, rel) if rel is not None and subject else None


def subject_of(question: str) -> list[str]:
    """The words a "which ... is sooner" question names its notes by."""
    read = _read_which(question)
    return read[0] if read else []


def asks(question: str) -> bool:
    """Whether `question` asks which of the notes on a subject ranks first."""
    return _read_which(question) is not None


def which_one(question: str, views: list, today: date, stem) -> Versus | None:  # noqa: ANN001
    """"Which trip is sooner", "which note is the oldest about baking": the
    notes the nouns and the topic name, ranked by the word asked."""
    read = _read_which(question)
    if read is None:
        return None
    (subject, (kind, low, key)) = read
    wanted = {stem(w) for w in subject}
    named = [v for v in views if wanted <= {stem(w) for w in (*v.words, *v.title_words, *v.filed_words)}]
    return _versus(key, _ranked(kind, named, today, low))


def said(versus: Versus, name) -> str:  # noqa: ANN001
    """The lead as one sentence, each note named by `name(view)`."""
    first, *rest = versus.rows
    text = f"{name(first.view)}{SAID[versus.key]}{first.shown}"
    for i, row in enumerate(rest):
        text += (SAID["figure_against"] if not i else " and ") + f"{row.shown}{SAID['figure_for']}{name(row.view)}"
    return text[:1].upper() + text[1:] + "."


def write(out, versus: Versus) -> None:  # noqa: ANN001
    """The lead in a composer answer: the winner, what it is, then each other
    with its figure or day."""
    first, *rest = versus.rows
    out.name(first.view, cap=True).t(versus.key).m(first.shown)
    for i, row in enumerate(rest):
        out.t("and" if i else "figure_against").m(row.shown).t("figure_for").name(row.view)
