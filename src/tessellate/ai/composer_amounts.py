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
_TOTAL = re.compile(r"^(?:what(?:'s| is| was)\s+)?(?:the\s+|my\s+|our\s+)?(?:grand\s+)?total\s+(?P<t>.+?)\W*$", re.I)
_TOTAL_HOW = re.compile(r"^how much (?:is|was|are) (?:the |my )?(?P<t>.+?) (?:in total|altogether|all together)\W*$", re.I)
_DIFFER = re.compile(
    r"^(?:what(?:'s| is)\s+)?(?:the\s+)?(?:difference|differences)\s+between\s+(?P<t>.+?)\W*$"
    r"|^compare\s+(?P<c>.+?)\W*$|^how (?:do|does|did) (?P<d>.+?) (?:compare|differ)\W*$",
    re.I,
)
_NOISE = re.compile(r"\b(?:for|in|of|on|the|my|our|a|an|and|vs|versus|two|both|to|with|spending|spend|spent|total)\b", re.I)


def lines(note: dict) -> list[tuple[str, float]]:
    """The note's "Label number" lines, in order."""
    out = []
    for raw in str(note.get("content") or "").splitlines()[1:]:
        found = _LINE.match(raw)
        if found:
            out.append((found.group("label").strip(" :-").strip(), float(found.group("n").replace(",", ""))))
    return out


def _amount(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".") if value != int(value) else f"{int(value):,}".replace(",", "")


def _priced(ctx: Ctx) -> list[dict]:
    return [n for n in ctx.notes if len(lines(n)) >= 2]


def _named(ctx: Ctx, words: list[str]) -> list[dict]:
    """Priced notes whose title holds every word named, best first."""
    wanted = study.content_stems(" ".join(words))
    if not wanted:
        return []
    out = []
    for note in _priced(ctx):
        have = set(study.content_stems(composer_frame.note_title(note)))
        if set(wanted) <= have:
            out.append(note)
    return out


def _total(ctx: Ctx, topic: str) -> Reply | None:
    words = [w for w in _NOISE.sub(" ", topic).split() if w]
    found = _named(ctx, words)
    if not found:
        return None
    note = found[0]
    rows = lines(note)
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


def _compare(ctx: Ctx, topic: str) -> Reply | None:
    pair = _pair(ctx, topic)
    if len(pair) < 2:
        return None
    first, second = pair
    a, b = dict(lines(first)), dict(lines(second))
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


def answer(ctx: Ctx) -> Reply | None:
    text = " ".join((ctx.question or "").split())
    total = _TOTAL.match(text) or _TOTAL_HOW.match(text)
    if total:
        return _total(ctx, total.group("t"))
    differ = _DIFFER.match(text)
    if differ:
        return _compare(ctx, differ.group("t") or differ.group("c") or differ.group("d") or "")
    return None
