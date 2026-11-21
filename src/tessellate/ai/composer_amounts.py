"""Notes that are lines of "Label number" (a budget, a price list): the total,
and how two such notes differ, worked out with no model (second composer
audit G11). "total budget for november" said the first line and "also" the
rest; "what's the difference between the two budgets" quoted a line of each.
A figure is only ever one the notes hold; the sum and the differences are
arithmetic over them.
"""

from __future__ import annotations

import re

from tessellate.ai import composer_frame, composer_study, study
from tessellate.ai.composer_study import Ctx, Reply

#: "Rent 650", "- Groceries: $140.50", "Eating out 90".
_LINE = re.compile(r"^\s*(?:[-*]\s*)?(?P<label>[A-Za-z][A-Za-z '&/-]{0,40}?)\s*[:=]?\s*[$£€]?\s*(?P<n>\d[\d,]*(?:\.\d+)?)\s*$")
#: "| Milk | £1.20 |": a table row of a label and a figure (G11: "how much more cheese than milk" over a price table).
_CELLS = re.compile(r"^\s*\|\s*(?P<label>[A-Za-z][A-Za-z '&/-]{0,40}?)\s*\|\s*[$£€]?\s*(?P<n>\d[\d,]*(?:\.\d+)?)\s*\|?\s*$")
_TOTAL = re.compile(r"^(?:what(?:'s| is| was)\s+)?(?:the\s+|my\s+|our\s+)?(?:grand\s+)?total\s+(?P<t>.+?)\W*$", re.I)
_TOTAL_HOW = re.compile(r"^how much (?:is|was|are) (?:the |my )?(?P<t>.+?) (?:in total|altogether|all together)\W*$", re.I)
_DIFFER = re.compile(
    r"^(?:what(?:'s| is)\s+)?(?:the\s+)?(?:difference|differences)\s+between\s+(?P<t>.+?)\W*$"
    r"|^compare\s+(?P<c>.+?)\W*$|^how (?:do|does|did) (?P<d>.+?) (?:compare|differ)\W*$",
    re.I,
)
#: "october budget versus november budget", "free vs plus plan": two sides, each a priced note's title words (F4).
_VERSUS = re.compile(r"^(?:compare\s+)?(?P<a>.+?)\s+(?:vs\.?|versus|compared (?:to|with)|against)\s+(?P<b>.+?)\W*$", re.I)
_NOISE = re.compile(r"\b(?:for|in|of|on|the|my|our|a|an|and|vs|versus|two|both|to|with|spending|spend|spent|total)\b", re.I)


def _sentence_run(raw: str) -> list[re.Match]:
    """"Rent 650. Groceries 140. Gym 45.": a line that is only "Label number" sentences, two or more."""
    parts = [p.strip() for p in re.split(r"(?<=\d)\.(?:\s+|$)", raw) if p.strip()]
    found = [_LINE.match(p) for p in parts]
    return [m for m in found if m] if len(parts) >= 2 and all(found) else []


def lines(note: dict, runs: bool = False) -> list[tuple[str, float]]:
    """The note's "Label number" lines in order; with `runs`, a line of such sentences read as that many
    (only "A versus B" asks it: "compare" and the figures reader are pinned to one label a line)."""
    out = []
    for raw in str(note.get("content") or "").splitlines()[1:]:
        found = [m] if (m := _LINE.match(raw) or _CELLS.match(raw)) else _sentence_run(raw) if runs else []
        out.extend((f.group("label").strip(" :-").strip(), float(f.group("n").replace(",", ""))) for f in found)
    return out


def _amount(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".") if value != int(value) else f"{int(value):,}".replace(",", "")


def _priced(ctx: Ctx, runs: bool = False) -> list[dict]:
    return [n for n in ctx.notes if len(lines(n, runs)) >= 2]


def _named(ctx: Ctx, words: list[str], runs: bool = False) -> list[dict]:
    """Priced notes whose title holds every word named, best first."""
    wanted = study.content_stems(" ".join(words))
    if not wanted:
        return []
    out = []
    for note in _priced(ctx, runs):
        have = set(study.content_stems(composer_frame.note_title(note)))
        if set(wanted) <= have:
            out.append(note)
    return out


def _total(ctx: Ctx, topic: str) -> Reply | None:
    words = [w for w in _NOISE.sub(" ", topic).split() if w]
    found = _named(ctx, words, True)
    if not found:
        return None
    note = found[0]
    rows = lines(note, True)
    total = sum(n for _l, n in rows)
    shown = ", ".join(f"{label} {_amount(n)}" for label, n in rows)
    return Reply(f"Your {composer_study._link(note)} note adds up to **{_amount(total)}**: {shown}.")  # noqa: SLF001


def _pair(ctx: Ctx, topic: str) -> list[dict]:
    """The two notes a comparison names: "the two budgets" is the newest two,
    "the october and november budgets" the two whose titles hold those words."""
    words = [w for w in _NOISE.sub(" ", topic).split() if w]
    if not words or not study.content_stems(words[-1]):
        return []
    pool = _named(ctx, [words[-1]])
    named = [n for n in pool if any(set(study.content_stems(w)) <= set(study.content_stems(composer_frame.note_title(n))) for w in words[:-1])]
    return (named if len(named) >= 2 else pool)[:2]


def _row(label: str, a: dict, b: dict, names: tuple[str, str]) -> tuple[str, bool]:
    """One label's line and whether it differs between the two notes."""
    if label in a and label in b:
        if a[label] == b[label]:
            return f"{label} {_amount(a[label])}", False
        gap = b[label] - a[label]
        return f"- {label}: {_amount(a[label])} in {names[0]}, {_amount(b[label])} in {names[1]} ({_amount(abs(gap))} {'more' if gap > 0 else 'less'})", True
    side, value = (names[0], a[label]) if label in a else (names[1], b[label])
    return f"- {label}: {_amount(value)}, only in {side}", True


def _side_note(ctx: Ctx, side: str) -> dict | None:
    words = [w for w in _NOISE.sub(" ", side).split() if w]
    return next(iter(_named(ctx, words, True)), None) if words else None


def _two_labels(ctx: Ctx, found: re.Match) -> Reply | None:
    """"free versus plus": two labels of one note set side by side, the figures and the gap."""
    first, second = _labelled(ctx, found.group("a")), _labelled(ctx, found.group("b"))
    both = next(((x, y) for x in first for y in second if x[0] is y[0] and x[1] != y[1]), None)
    if not both:
        return None
    (note, a_label, a_value), (_n, b_label, b_value) = both
    gap = b_value - a_value
    tail = "the same" if gap == 0 else f"{_amount(abs(gap))} {'more' if gap > 0 else 'less'} for {b_label}"
    return Reply(f"{a_label} is {_amount(a_value)} and {b_label} is {_amount(b_value)}, {tail}, from {composer_study._link(note)}.")  # noqa: SLF001


def _versus(ctx: Ctx, found: re.Match) -> Reply | None:
    """"A versus B" where each side names one priced note: the same line-by-line reading as "compare";
    where the sides are two labels of one note, the two figures."""
    first, second = _side_note(ctx, found.group("a")), _side_note(ctx, found.group("b"))
    if not first or not second or first is second or not {k for k, _ in lines(first, True)} & {k for k, _ in lines(second, True)}:
        return _two_labels(ctx, found)  # two notes with no label in common have nothing to set side by side
    return _compare_notes(first, second, True)


def _compare(ctx: Ctx, topic: str) -> Reply | None:
    pair = _pair(ctx, topic)
    return _compare_notes(*pair) if len(pair) >= 2 else None


def _compare_notes(first: dict, second: dict, runs: bool = False) -> Reply:
    a, b = dict(lines(first, runs)), dict(lines(second, runs))
    names = (composer_frame.note_title(first), composer_frame.note_title(second))
    rows = [_row(label, a, b, names) for label in dict.fromkeys([*a, *b])]
    differ, same = [r for r, d in rows if d], [r for r, d in rows if not d]
    total_a, total_b = sum(a.values()), sum(b.values())
    gap = f", {_amount(abs(total_b - total_a))} {'more' if total_b > total_a else 'less'} in the second." if total_a != total_b else ", the same."
    out = [f"{composer_study._link(first)} comes to {_amount(total_a)} and {composer_study._link(second)} to {_amount(total_b)}{gap}"]  # noqa: SLF001
    if differ:
        out += ["", "What differs:", *differ]
    if same:
        out += ["", "The same in both: " + ", ".join(same) + "."]
    return Reply("\n".join(out))


_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_WHICH = re.compile(
    r"^(?:which|what)(?:'s|\s+is|\s+are)?(?:\s+one)?(?:\s+is)?\s+(?P<cmp>cheaper|dearer|pricier|more expensive|less expensive|costs? more|costs? less)\W+"
    r"(?:the\s+)?(?P<a>[a-z][a-z '&/-]{0,30}?)\s+(?:or|vs\.?|versus)\s+(?:the\s+)?(?P<b>[a-z][a-z '&/-]{0,30}?)\W*$",
    re.I,
)
_MORE = re.compile(
    rf"^how much (?P<dir>more|less) did (?:i|we) (?:spend|pay) (?:on |for |at )?(?P<label>.+?) in (?P<m1>{_MONTHS})"
    rf"(?: (?:than|compared (?:to|with)|vs\.?|versus) (?:in )?(?P<m2>{_MONTHS}))?\W*$",
    re.I,
)
#: "how much more is cheese than milk", "how much more rent than groceries in november": two labels of one note (G11).
_GAP = re.compile(
    r"^how much (?P<dir>more|less) (?:(?:is|was|are|does|do|did) )?(?:the |a )?(?P<a>[a-z][a-z '&/-]{0,30}?)(?: cost| costs)? than (?:the |a )?"
    rf"(?P<b>[a-z][a-z '&/-]{{0,30}}?)(?: in (?P<m>{_MONTHS}))?\W*$",
    re.I,
)
_LESS_WORDS = ("cheaper", "less expensive", "cost less", "costs less")


def _labelled(ctx: Ctx, words: str, notes: list[dict] | None = None) -> list[tuple[dict, str, float]]:
    """Each priced note's line whose label is exactly `words` (by stem), as (note, label, figure)."""
    wanted = set(study.content_stems(words))
    return [(n, label, value) for n in (notes if notes is not None else _priced(ctx, True)) for label, value in lines(n, True) if wanted and set(study.content_stems(label)) == wanted]


def _which(ctx: Ctx, found: re.Match) -> Reply | None:
    """"which is cheaper, free or plus": the two labels' figures, from the one note that holds both."""
    first, second = _labelled(ctx, found.group("a")), _labelled(ctx, found.group("b"))
    both = next(((x, y) for x in first for y in second if x[0] is y[0]), None)
    if not both:
        return None
    (note, a_label, a_value), (_n, b_label, b_value) = both
    cmp = found.group("cmp").lower()
    if a_value == b_value:
        return Reply(f"{a_label} and {b_label} are the same, {_amount(a_value)} each, in {composer_study._link(note)}.")  # noqa: SLF001
    lower = cmp in _LESS_WORDS
    win, other = ((a_label, a_value), (b_label, b_value)) if (a_value < b_value) == lower else ((b_label, b_value), (a_label, a_value))
    verb = f"costs {cmp.split()[-1]}" if cmp.startswith("cost") else f"is {cmp}"
    return Reply(f"{win[0]} {verb}: {_amount(win[1])} against {_amount(other[1])} for {other[0]}, from {composer_study._link(note)}.")  # noqa: SLF001


def _gap(ctx: Ctx, found: re.Match) -> Reply | None:
    """Two labels of one note, the figures and the difference in the direction asked (a month names the note)."""
    notes = [n for n in _priced(ctx, True) if not found.group("m") or _titled_month(n, found.group("m"))]
    first, second = _labelled(ctx, found.group("a"), notes), _labelled(ctx, found.group("b"), notes)
    both = next(((x, y) for x in first for y in second if x[0] is y[0] and x[1] != y[1]), None)
    if not both:
        return None
    (note, a_label, a_value), (_n, b_label, b_value) = both
    gap = a_value - b_value
    facts = f"{a_label} is {_amount(a_value)} and {b_label} is {_amount(b_value)}, from {composer_study._link(note)}."  # noqa: SLF001
    if gap == 0:
        return Reply(f"The same: {facts}")
    word = "more" if gap > 0 else "less"
    asked_more = found.group("dir").lower() == "more"
    lead = f"{_amount(abs(gap))} {word}" if (gap > 0) == asked_more else f"No, {_amount(abs(gap))} {word}"
    return Reply(f"{lead}: {facts}")


def _titled_month(note: dict, month: str) -> bool:
    return month.lower() in composer_frame.note_title(note).lower()


def _more(ctx: Ctx, found: re.Match) -> Reply | None:
    """"how much more did I spend eating out in october": one label in two notes, the month asked against the other."""
    rows = _labelled(ctx, found.group("label"))
    first = next((r for r in rows if _titled_month(r[0], found.group("m1"))), None)
    rest = [r for r in rows if r is not first and (not found.group("m2") or _titled_month(r[0], found.group("m2")))]
    if first is None or not rest:
        return None
    other = rest[0]
    gap = first[2] - other[2]
    asked_more = found.group("dir").lower() == "more"
    title_month = re.search(_MONTHS, composer_frame.note_title(other[0]), re.I)
    m1, m2 = found.group("m1").capitalize(), (found.group("m2") or (title_month.group(0) if title_month else "")).capitalize() or composer_frame.note_title(other[0])
    facts = f"{first[1]} was {_amount(first[2])} in {m1} ({composer_study._link(first[0])}) and {_amount(other[2])} in {m2} ({composer_study._link(other[0])})."  # noqa: SLF001
    if gap == 0:
        return Reply(f"The same: {facts}")
    word = "more" if gap > 0 else "less"
    lead = f"{_amount(abs(gap))} {word}" if (gap > 0) == asked_more else f"No, {_amount(abs(gap))} {word}"
    return Reply(f"{lead} in {m1}: {facts}")


#: "how much is Plus a year", "what does Plus cost annually", "the yearly cost of Plus": the subject is the words between.
_YEARLY = re.compile(
    r"^(?:so |and )?(?:how much|what)(?:'s| is| does| would| will| do| are)?\s+(?:the\s+)?(?:(?:yearly|annual)\s+(?:cost|price)\s+(?:of\s+)?(?P<a>.+?)"
    r"|(?:(?:is|does|would|will|for)\s+)*(?P<b>.+?)\s+(?:cost\s+|be\s+|come to\s+)?(?:a|per|each|for a|in a|over a)\s+year|(?P<c>.+?)\s+(?:cost\s+)?(?:annually|yearly|per annum))\W*$",
    re.I,
)
_MONTHLY = re.compile(r"(?P<cur>[$£€])\s?(?P<n>\d[\d,]*(?:\.\d+)?)\s*(?:a|per|/|each|every)\s*month\b|(?P<cur2>[$£€])\s?(?P<m>\d[\d,]*(?:\.\d+)?)\s*monthly\b", re.I)
_YEARLY_PRICE = re.compile(r"(?P<cur>[$£€])\s?(?P<n>\d[\d,]*(?:\.\d+)?)(?=[^.\n]{0,24}\b(?:a year|per year|yearly|annual\w*)\b)|\b(?:a year|per year|yearly|annual\w*)\b[^.\n$£€]{0,24}(?P<cur2>[$£€])\s?(?P<m>\d[\d,]*(?:\.\d+)?)", re.I)
_FILLER = frozenset({"plan", "plans", "subscription", "price", "cost", "cost", "membership", "fee", "tier"})


def _monthly_price(ctx: Ctx, subject: list[str]) -> tuple[dict, re.Match] | None:
    """The first note sentence naming the subject with a price per month, and that price."""
    for note in ctx.notes:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(note.get("content") or "")):
            monthly = _MONTHLY.search(sentence)
            if monthly and set(subject) <= set(study.content_stems(sentence)):
                return note, monthly
    return None


def _yearly(ctx: Ctx, text: str) -> Reply | None:
    """A year of a price the notes state per month: twelve times it, with the note it came from (L-chat-244)."""
    found = _YEARLY.match(text)
    name = ((found.group("a") or found.group("b") or found.group("c") or "").strip()) if found else ""
    subject = [w for w in study.content_stems(name) if w not in _FILLER]
    hit = _monthly_price(ctx, subject) if subject else None
    if hit is None:
        return None
    note, monthly = hit
    price = float((monthly.group("n") or monthly.group("m")).replace(",", ""))
    cur = monthly.group("cur") or monthly.group("cur2")
    said = f"{cur}{_amount(price * 12)} a year. {name[:1].upper() + name[1:]} is {cur}{_amount(price)} a month, and a year is twelve of those ({composer_study._link(note)})."  # noqa: SLF001
    plain = _YEARLY_PRICE.search(str(note.get("content") or ""))
    if plain:
        said += f" The note also names {plain.group('cur') or plain.group('cur2')}{_amount(float((plain.group('n') or plain.group('m')).replace(',', '')))} for a year."
    return Reply(said)


def answer(ctx: Ctx) -> Reply | None:
    text = " ".join((ctx.question or "").split())
    return _yearly(ctx, text) or _labelled_answer(ctx, text)


def _labelled_answer(ctx: Ctx, text: str) -> Reply | None:
    which, more = _WHICH.match(text), _MORE.match(text)
    if which or more:
        return _which(ctx, which) if which else _more(ctx, more)
    gap = _GAP.match(text)
    if gap and (said := _gap(ctx, gap)):
        return said
    total = _TOTAL.match(text) or _TOTAL_HOW.match(text)
    if total:
        return _total(ctx, total.group("t"))
    versus = _VERSUS.match(text)
    if versus and (said := _versus(ctx, versus)):
        return said
    differ = _DIFFER.match(text)
    if differ:
        return _compare(ctx, differ.group("t") or differ.group("c") or differ.group("d") or "")
    return None
