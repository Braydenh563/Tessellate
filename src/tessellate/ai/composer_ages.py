"""Who is older: "who is older, Anna or Tom" read from the ages the notes give.

An age is a sentence that says it of the person ("Tom is 41", "Anna (34)",
"aged 34", "34 years old") or a birth year ("born in 1984"). Two ages are
compared; when the notes do not say one, the reply says so plainly instead of
answering a gift line (BC4 E9). Nothing is guessed from a birthday alone.
"""

from __future__ import annotations

import re

from tessellate.ai.composer_study import Ctx, Reply

_NAME = r"[A-Za-z][\w'’ -]{0,24}?"
_ASK = (
    re.compile(rf"^(?:who|which(?: one)?)(?:'s|\s+is|\s+are)?\s+(?P<dir>older|younger)\W+(?:out of\s+|between\s+)?(?:the\s+)?(?P<a>{_NAME})\s+(?:or|vs\.?|versus|and)\s+(?:the\s+)?(?P<b>{_NAME})\W*$", re.I),
    re.compile(rf"^(?:the\s+)?(?P<a>{_NAME})\s+(?:or|vs\.?|versus)\s+(?:the\s+)?(?P<b>{_NAME})\W+(?:who|which(?: one)?)(?:'s|\s+is)?\s+(?P<dir>older|younger)\W*$", re.I),
)
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
#: A figure that is an age, not a date, a measure or a count.
_NOT_AGE = rf"(?!\s*(?:km|kg|%|:|/|-|st\b|nd\b|rd\b|th\b|{_MONTH}\b)|\d)"


def _ages(name: str, notes: list[dict], year: int) -> tuple[int, str, int | None] | None:
    """(birth year estimate, the way it was said, the note) for `name`, from the first note that says it."""
    who = re.escape(name)
    for note in notes:
        text = str(note.get("content") or "")
        for pattern, is_year in (
            (rf"\b{who}\b['’]?s?\s+(?:is|was|turned|turns)\s+(\d{{1,3}}){_NOT_AGE}", False),
            (rf"\b{who}\b\s*\((\d{{1,3}})\)", False),
            (rf"\b{who}\b[^.\n]{{0,30}}?\baged?\s+(\d{{1,3}}){_NOT_AGE}", False),
            (rf"\b{who}\b[^.\n]{{0,30}}?\b(\d{{1,3}})\s+years?\s+old", False),
            (rf"\b{who}\b[^.\n]{{0,30}}?\bborn(?:\s+in|\s+on)?\s+(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\s+|{_MONTH}\s+(?:\d{{1,2}},?\s+)?)?((?:19|20)\d\d)\b", True),
        ):
            found = re.search(pattern, text, re.I)
            if found and (is_year or 0 < int(found.group(1)) < 121):
                value = int(found.group(1))
                return (value, f"born {value}", note.get("id")) if is_year else (year - value, str(value), note.get("id"))
    return None


def answer(ctx: Ctx) -> Reply | None:
    said = read(ctx.question, ctx.notes, ctx.now.year)
    return Reply(said[0]) if said else None


def read(question: str, notes: list[dict], year: int) -> tuple[str, int | None] | None:
    """(the reply, the id of a note it rests on) for a who-is-older ask, else None."""
    text = " ".join((question or "").split())
    found = next((m for pat in _ASK if (m := pat.match(text))), None)
    if not found:
        return None
    names = [found.group("a").strip(" ,"), found.group("b").strip(" ,")]
    names = [n[:1].upper() + n[1:] if n.islower() else n for n in names]
    said = [_ages(n, notes, year) for n in names]
    cited = next((s[2] for s in said if s), None)
    gap = _gap(names, said, cited)
    if gap:
        return gap
    return _compare(names, said, found.group("dir").lower() == "older", cited)


def _gap(names: list[str], said: list, cited: int | None) -> tuple[str, int | None] | None:
    """The reply when the notes do not give both ages, else None."""
    if said[0] is None and said[1] is None:
        return f"Your notes do not say how old {names[0]} or {names[1]} is.", None
    for i in (0, 1):
        if said[i] is None:
            return f"Your notes say {_says(names[1 - i], said[1 - i][1])}, but they do not say how old {names[i]} is.", cited
    return None


def _compare(names: list[str], said: list, older: bool, cited: int | None) -> tuple[str, int | None]:
    (ya, wa, _), (yb, wb, _) = said
    if ya == yb:
        return f"{names[0]} and {names[1]} are the same age going by your notes ({wa}).", cited
    first_older = ya < yb
    lead = names[0] if first_older == older else names[1]
    other = names[1] if lead == names[0] else names[0]
    word = "older" if older else "younger"
    lead_said, other_said = (wa, wb) if lead == names[0] else (wb, wa)
    return f"{lead} is {word}: {lead_said} against {other_said} for {other}.", cited


def _says(name: str, how: str) -> str:
    return f"{name} was {how.replace('born ', 'born in ')}" if how.startswith("born") else f"{name} is {how}"



#: Asking what the to-do list holds (`_TODO_ASK`): the note titled by `_TODO_TITLES`, or a checklist (R3-31).
_TODO_ASK = re.compile(r"^(?:what(?:'s|’s| is| are)?|show me|read me)\s+(?:in|inside|on)\s+(?:my |the |our )?(?:to-?do|todo|to do)(?:\s+(?:list|note))?\W*$", re.I)
_TODO_TITLES = frozenset({"todo", "to do", "to-do", "todos", "to dos", "to-dos", "todo list", "to do list", "to-do list"})
_CHECKBOX = re.compile(r"^\s*[-*+]\s*\[[ xX]\]", re.M)


def no_todo(question: str, notes: list[dict]) -> str | None:
    """The plain miss for a to-do ask when no note has a `_TODO_TITLES` title and none holds a checklist, else None."""
    if not _TODO_ASK.match(" ".join((question or "").split())):
        return None
    for note in notes:
        first = str(note.get("content") or "").lstrip().split("\n", 1)[0].lstrip("# ").strip().lower().rstrip(":")
        if first in _TODO_TITLES or _CHECKBOX.search(str(note.get("content") or "")):
            return None
    return "You have no note called Todo, and no checklist yet. Write one with lines like “- [ ] buy stamps”."
