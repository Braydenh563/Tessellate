"""A long note said briefly (INBOX 1665 c, the owner: the cloud computing
definition and the subjects sentence were copied whole, the second with a
spaced hyphen joining its clauses).

A note over `BRIEF_WORDS` words is told by its gist: the asides in dashes
go, then the first sentence alone, then the first whole clause that fits.
A spaced hyphen or dash is never kept as it was written: before a capital it
introduces a list ("subjects: Tangible Design, ..."), else it is a comma.
Only words the person wrote are kept; nothing is added.
"""

from __future__ import annotations

import re

#: About how many words a note may run before it is said by its gist.
BRIEF_WORDS = 25
#: The fewest words a cut-back clause may keep: less is a lead, not the point.
MIN_HEAD = 12
#: A dash or hyphen with a space each side, the way a person joins clauses.
_SPACED_DASH = re.compile(r"\s[-\u2013\u2014]\s")
#: An aside between two spaced dashes ("services, including servers, over").
_ASIDE = re.compile(r"\s[-\u2013\u2014]\s[^-\u2013\u2014]*?\s[-\u2013\u2014]\s")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])")
_CLAUSE_BREAK = re.compile(r",\s+(?=(?:and|but|so|because|which|then|while)\b)|;\s+|,\s+")
#: Words a clause may not end on (cut after one, it dangles).
_DANGLES = frozenset("and or but nor so then the a an to of with for in on at by as from into that which who if when while because than my your our".split())


def _count(text: str) -> int:
    return len(text.split())


def unjoined(text: str) -> str:
    """`text` with each spaced hyphen or dash made a colon before a capital
    and a comma elsewhere, never kept as it was written."""
    return _SPACED_DASH.sub(lambda m: ": " if text[m.end():m.end() + 1].isupper() else ", ", text)


def _whole_head(text: str, limit: int) -> str:
    """The longest run of `text` up to a clause break that fits `limit` words,
    ending on a whole word; "" when no such break leaves enough to say."""
    best = ""
    for found in _CLAUSE_BREAK.finditer(text):
        head = text[: found.start()].rstrip(" ,;:")
        words = head.split()
        if _count(head) > limit:
            break
        #: A head that is only a lead ("four weeks ago, on 8 October") is not the gist.
        if _count(head) >= MIN_HEAD and words[-1].lower().strip(",;:") not in _DANGLES:
            best = head
    return best


def brief(text: str, limit: int = BRIEF_WORDS, squeeze: bool = False) -> str:
    """`text` as it is when it is short and has no spaced dash; else its gist.
    `squeeze` says the note it is of is long: its dash asides go even when
    this sentence alone is short."""
    said = text.strip()
    if squeeze:
        said = " ".join(_ASIDE.sub(" ", said).split())
    if _count(said) > limit:
        said = " ".join(_ASIDE.sub(" ", said).split())
        if _count(said) > limit:
            said = _SENTENCE_END.split(said, maxsplit=1)[0]
        if _count(said) > limit:
            said = unjoined(said)
            head = _whole_head(said, limit)
            if head:
                said = head
        #: Told under a line that closes it with its own stop.
        said = said.rstrip(". ")
    return unjoined(said)
