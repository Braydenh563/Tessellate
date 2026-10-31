"""A question an answer suggests is a button, never text to retype (INBOX 1497).

The owner, 2026-10-31, on a Guide answer that ended `If it helps, ask me "how
do I attach a note to a chat" and I will show you.`: "if it suggests a follow
up question, I want a button to one click ask". Every surface that suggests a
question (the Guide, Chat, Ask; composed or model) says it in the one shape
`ask me “...”` and this module lifts that quoted question out as a chip, so
no surface needs its own parser and a new wording is a chip the day it is
written. `tests/test_ask_chips.py` checks that every suggesting template in
the help and the composer lifts.
"""

from __future__ import annotations

import re

#: A quote opened within a few words of an asking cue: "ask me “...”", "try
#: asking “...”", "a good next question here: “...”". The words between the
#: cue and the quote are bounded and hold no quote, so nothing backtracks.
_CUE = r"(?:ask(?:ing)?(?: me| it| the guide| atlas)?|try(?: asking)?|next question(?: here)?|you could say|say)"
_SUGGESTED = re.compile(rf"\b{_CUE}\b[^“”\"\n]{{0,32}}?[“\"]([^“”\"\n]{{3,120}}?)[”\"]", re.I)
#: What a suggested question may start with: a question word, or an order the
#: composer reads ("show me", "list", "open").
_ASKABLE = re.compile(
    r"^(?:what|when|where|who|whom|whose|which|why|how|is|are|was|were|do|does|did|can|could|will|would|should|have|has|"
    r"show|tell|list|find|open|give|summari[sz]e|compare|remind|explain|help|any|anything)\b",
    re.I,
)


#: A second suggestion chained on the first: "ask me “a” or “b”". The space
#: before it is skipped by hand (`_quoted`), so the pattern never opens on a
#: run of spaces it might have to give back (CodeQL 1899).
_CHAINED = re.compile(r"(?:(?:,|or|and|then)\s*)?[“\"]([^“”\"\n]{3,120}?)[”\"]", re.I)


def _quoted(text: str) -> list[str]:
    out: list[str] = []
    for match in _SUGGESTED.finditer(text):
        out.append(match.group(1))
        at = match.end()
        while True:
            while at < len(text) and text[at].isspace():
                at += 1
            if (more := _CHAINED.match(text, at)) is None:
                break
            out.append(more.group(1))
            at = more.end()
    return out


def lift(text: str, *, limit: int = 3) -> list[str]:
    """The questions `text` suggests, in order and without repeats, as the
    person would type them (a capital first, a question mark for a question
    word); at most `limit`."""
    found: list[str] = []
    for quoted in _quoted(text or ""):
        ask = " ".join(quoted.split()).strip(" ,;:")
        if not _ASKABLE.match(ask):
            continue
        ask = ask[:1].upper() + ask[1:]
        if not ask.endswith(("?", ".", "!")):
            ask += "?" if re.match(r"(?:what|when|where|who|whom|whose|which|why|how|is|are|was|were|do|does|did|can|could|will|would|should|have|has)\b", ask, re.I) else ""
        if ask not in found:
            found.append(ask)
    return found[:limit]
