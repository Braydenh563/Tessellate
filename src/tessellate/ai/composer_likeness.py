"""A product name is not the thing it shares a stem with (R9-11, composer audit round 9).

"What do I know about apples" matches the note titled "Apple watch" by stem, though the question wrote the plain
plural and a note ("Apple crumble": "4 apples") does say that exact word. A note is set aside only when all of
this holds: the question's word is not in its title, its title has the stem only as a capitalised first word of a
product name ("Apple watch", not "Meeting with Raj"), its text says the word nowhere else, and another note found
does write the question's exact word."""

from __future__ import annotations

import re

from tessellate.ai.composer_ask import _stem

_WORD = re.compile(r"[A-Za-z']{4,}")
_FUNCTION = frozenset({"with", "and", "of", "for", "in", "on", "at", "to", "the", "a", "an", "from", "by", "or", "vs"})


#: "Book club", "Reading list": the second word says the note is a group or a collection of the first, so the
#: note is about the plural the question wrote ("books"), where "Apple watch" is a different thing (W7b found-not-fixed:
#: "what do I know about books" lost "Book club notes" that "what do I have on books" kept).
_COLLECTIVE = frozenset({"club", "clubs", "list", "lists", "shelf", "shelves", "collection", "library", "group", "groups"})


def _product_name(title: str, stems: set[str], asked: set[str]) -> bool:
    words = title.split()
    return (
        len(words) >= 2 and words[0][:1].isupper() and words[0].lower() not in asked and _stem(words[0].lower()) in stems
        and words[1].lower() not in _FUNCTION and words[1].lower() not in _COLLECTIVE
    )


def set_aside(views: list, question: str) -> set[int]:
    """The ids of the notes in `views` that hold the question's words only as a product name."""
    asked = {w.lower() for w in _WORD.findall(question[:500])}
    stems = {_stem(w) for w in asked}
    spelled = {w for w in asked if any(re.search(rf"\b{re.escape(w)}\b", str(v.note.get("content") or ""), re.I) for v in views)}
    if not spelled:
        return set()
    out = set()
    for view in views:
        title = str(view.title or "")
        rest = str(view.note.get("content") or "").replace(title, " ", 1).lower()
        if _product_name(title, stems, asked) and not any(_stem(w) in stems for w in _WORD.findall(rest)):
            out.add(view.id)
    return out
