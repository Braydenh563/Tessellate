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

import bisect
import itertools
import re

#: About how many words a note may run before it is said by its gist.
BRIEF_WORDS = 25
#: The fewest words a cut-back clause may keep: less is a lead, not the point.
MIN_HEAD = 12
#: A dash or hyphen with a space each side, the way a person joins clauses.
_SPACED_DASH = re.compile(r"\s[-\u2013\u2014]\s")
#: An aside between two spaced dashes ("services, including servers, over").
_ASIDE = re.compile(r"\s[-\u2013\u2014]\s[^-\u2013\u2014]*?\s[-\u2013\u2014]\s")
#: One space, no loop: `brief` folds spaces before it splits, and CodeQL reads a `\s+` here as polynomial (PR 216).
_SENTENCE_END = re.compile(r"(?<=[.!?]) (?=[A-Z0-9\"“(])")
_KEPT_RUN = re.compile(r"[^ ,;:]+")
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
    ending on a whole word; "" when no such break leaves enough to say.

    Linear, not one slice and split per break: `", " * 25000` took 1.6 s
    that way (PR 216). Each head is `text[:k]`, k being the break with the
    trailing " ,;:" taken off, and its word count is the words starting before k."""
    #: Only the first `limit` + 1 words are read: a break past them counts more than `limit` and ends
    #: the walk. k, where text[:break].rstrip(" ,;:") ends, is the end of the last run of other
    #: characters before the break, walked alongside the breaks (a loop per character and lists over
    #: every word took 67 ms on a 100,000-character first sentence, CI 3.11).
    words = [(m.start(), m.end()) for m in itertools.islice(re.finditer(r"\S+", text), limit + 1)]
    starts = [start for start, _ in words]
    runs = _KEPT_RUN.finditer(text)
    run = next(runs, None)
    k = best = 0
    for found in _CLAUSE_BREAK.finditer(text):
        while run is not None and run.end() <= found.start():
            k = run.end()
            run = next(runs, None)
        count = bisect.bisect_left(starts, k)
        if count > limit:
            break
        #: A head that is only a lead ("four weeks ago, on 8 October") is not the gist.
        last = text[words[count - 1][0]:min(words[count - 1][1], k)] if count else ""
        if count >= MIN_HEAD and last.lower().strip(",;:") not in _DANGLES:
            best = k
    return text[:best]


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


#: The most sentences of one note the model's brief adds for holding a word of the question.
MATCHED_PER_NOTE = 3
#: Only a short match ("Too dense again.") takes the sentence after it; a full sentence says its own news, and the
#: brief keeps its saving on the showcase notes (tests/test_composer_brief.py).
SHORT_MATCH = 4


def matching(sentences: list, stems: set[str], holds, chosen: list = ()) -> list:  # noqa: ANN001
    """The sentences of a note that hold a word of the question, in the note's order, at most
    `MATCHED_PER_NOTE`: a note marked "(matched: meditation)" never loses the sentence with the word,
    whatever the composer's own pick was (R9-13)."""
    hits = [s for s in sentences if any(holds(st, set(s.words)) for st in stems)][:MATCHED_PER_NOTE]
    #: A word the composer's own pick already holds needs no second sentence: the brief keeps its saving.
    open_stems = {st for st in stems if not any(holds(st, set(c.words)) for c in chosen)}
    found = [s for s in hits if any(holds(st, set(s.words)) for st in open_stems)]
    #: "Too dense again." is followed by what to do about it: a short match takes the sentence after it.
    after = [sentences[sentences.index(s) + 1] for s in hits if len(s.words) <= SHORT_MATCH and sentences.index(s) + 1 < len(sentences)]
    return sorted({id(s): s for s in [*found, *after]}.values(), key=lambda s: s.order)
