"""The entity card's measured line (CHAT_PLAN A23, L-chat-99): when a person or
thing was first and last written about, and the names that share their notes.
The count and the two best sentences are the answer's own (`composer_digest._who`);
this adds what only the aggregate knows. No model."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from tessellate.ai.insights import _MONTHS, _day

#: A capitalised word that follows a lower-case word or a comma is a name; one that opens a sentence may only be a word.
_NAME = re.compile(r"(?<=[a-z,] )[A-Z][a-z]{2,}\b")
_NOT_NAMES = frozenset(_MONTHS) | {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Christmas", "Easter"}
BESIDE = 2


def _list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _beside(notes: dict, own: set[str]) -> list[str]:
    """The names most often written in the same notes, never the card's own."""
    beside: Counter = Counter()
    for v in notes.values():
        beside.update({m.group(0) for m in _NAME.finditer(str(v.note.get("content") or ""))} - _NOT_NAMES)
    return [n for n, c in sorted(beside.items(), key=lambda kv: (-kv[1], kv[0])) if c >= 1 and n.lower() not in own][:3]


def card(name: str, found: list, today: date) -> str:
    """"First mentioned 25 September, last 15 October; named beside Anna and
    Tom." `found` is `(NoteView, Sentence)` pairs; "" when there is nothing
    to add (one day, no shared names)."""
    notes = {v.id: v for v, _s in found}
    days = sorted(v.written for v in notes.values() if v.written)
    top = _beside(notes, {w.lower() for w in name.split()})
    dated = f"First mentioned {_day(days[0], today)}, last {_day(days[-1], today)}" if len(notes) > 1 and len(days) > 1 and days[0] != days[-1] else ""
    near = f"named beside {_list(top)}" if top else ""
    if dated and near:
        return f"{dated}; {near}."
    return f"{dated}." if dated else (f"{near[:1].upper()}{near[1:]}." if near else "")
