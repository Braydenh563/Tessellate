"""Why two notes are linked, said from the notes themselves (INBOX 691).

The owner: "so many notes get the reason 'similar in meaning' ... needs to
be world class". `manager._deduce_reason` compares two vectors, and a vector
has no words for what it found, so every link a person did not explain read
the same four words: measured on the showcase notebook, 48 of 87 links.

The two notes usually say more than that on their face, and none of it needs
a model:

1. **One names the other**: a `[[Kiln plan]]`, or the other note's opening
   words written out in full. "“Glaze tests” names “Kiln plan”".
2. **Shared tags**, rarest first, leaving out a tag most of the notebook
   carries (it says nothing about these two). "Both tagged #schedule,
   #university".
3. **Shared named things**: a person, a place, a product. An entity both
   notes mention (`EntityMention`), or a capitalised name both write, one of
   them mid-sentence (a capital at the start of a sentence is grammar, not a
   name). "Both mention Alfa Pendular and Porto".
4. **Shared rare words**: a word only a few notes use. "Both mention “kiln”".
5. **Same category, written close together**: within a week, never
   Uncategorised. "Written two days apart, both in Travel".

When none of those is found, one sentence from each note that share two
plain words is quoted (`_quoted_pair`). The first two clues found are joined; the sentence stays under `MAX_CHARS`
(the AI audit's own cap, `ai/links.MAX_REASON_CHARS`). When none is found the
caller keeps "similar in meaning" and shows its strength in words
(`strength_word`).

Pure on purpose, and with no import from the rest of the app: `manager`
imports this, so it must import nothing that imports `manager`. The word
rules are a small copy of `ai/lexical_filing.tokens` for that reason.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

#: A reason longer than this reads as a paragraph in a tooltip.
MAX_CHARS = 80

#: The words `manager._deduce_reason` writes; a reason that starts with them
#: is the generic one, whatever follows ("..., and around the same time").
GENERIC_PREFIX = "similar in meaning"

#: How close the two notes' vectors were, in words (the score is the cosine
#: `reason_confidence` keeps; the link bar is 0.55).
STRONG_AT = 0.75
SOME_AT = 0.65

#: A clue held by more than this share of the notebook says nothing about
#: two notes in particular. Tags are chosen labels, so they may be commoner.
TAG_SHARE = 0.25
NAME_SHARE = 0.15
WORD_SHARE = 0.04
#: ...but in a small notebook anything held by this few is still rare (a
#: plain word, the weakest clue, needs to be rarer still).
RARE_FLOOR = 3
WORD_FLOOR = 2

#: Close in time, for the category clue.
CLOSE_DAYS = 7

UNCATEGORISED = "uncategorised"

_STOP = frozenset(
    """a about after again all also am an and any are as at be because been
    before being but by can could did do does doing done for from get got had
    has have having he her here him his how i if in into is it its just like
    me more most my no not now of off on once only or other our out over own
    really same she should so some still such than that the their them then
    there these they this those through to too up us very was we were what
    when where which while who why will with would you your yes ok okay im
    ive dont didnt cant wont thats today tomorrow yesterday note notes thing
    things need want make made going good great""".split()
)

#: Ordinary words that are rare in one notebook by chance and say nothing
#: about two notes when shared ("both mention “month”"): measured on the
#: showcase notebook, each of these was a clue before this list.
_PLAIN = frozenset(
    """month week year time half easy long short work trip sign plan list idea
    start first last next little much many every back keep maybe think feel
    thing once twice three four five early late open close high low small
    large big best better right left""".split()
)

#: Capitalised, but a date word rather than a name: every note has a Monday.
_CALENDAR = frozenset(
    """monday tuesday wednesday thursday friday saturday sunday january
    february march april may june july august september october november
    december""".split()
)

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
#: A run of capitalised words, joined by single spaces ("Alfa Pendular").
_CAPS = re.compile(r"[A-Z][\w'’-]*(?: [A-Z][\w'’-]*)*")
_WIKI = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
_NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven")


@dataclass(frozen=True)
class PairNote:
    """What the wording reads of one note. `text` is its readable text."""

    id: int
    text: str
    tags: tuple[str, ...] = ()
    category: str | None = None
    created_at: datetime | None = None
    #: Names of the entities it mentions (people, places, projects).
    entities: frozenset[str] = frozenset()


def tokens(text: str) -> list[str]:
    """Lower-case words, stop words out, a light plural fold."""
    out = []
    for word in _WORD.findall((text or "").lower()):
        word = word.replace("'", "")
        if len(word) < 4 or word in _STOP or word.isdigit():
            continue
        if len(word) > 4 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        out.append(word)
    return out


def _at_start(text: str, i: int) -> bool:
    """True when the word at `i` opens a sentence, a line or a list item,
    where a capital is grammar rather than a name."""
    j = i - 1
    while j >= 0 and text[j] in " \t\"'“‘([*_#>+-":
        j -= 1
    return j < 0 or text[j] in "\n.!?:;"


def _names(text: str) -> tuple[dict[str, str], set[str]]:
    """Capitalised runs in `text`: every one (key -> as written) and the keys
    written mid-sentence, where a capital means a name."""
    found: dict[str, str] = {}
    mid: set[str] = set()
    plain = _WIKI.sub(lambda m: m.group(1), text or "")
    for match in _CAPS.finditer(plain):
        words = match.group(0).split(" ")
        start = match.start()
        #: "In Porto": the capital on "In" is the sentence's, not the name's.
        while words and words[0].casefold() in _STOP:
            start += len(words.pop(0)) + 1
        shown = " ".join(words).strip("'’-")
        key = shown.casefold()
        if len(shown) < 3 or key in _CALENDAR:
            continue
        found.setdefault(key, shown)
        if not _at_start(plain, start):
            mid.add(key)
    return found, mid


@dataclass
class Counts:
    """How many notes hold each clue, so a common one can be left out."""

    total: int
    tag_df: Counter = field(default_factory=Counter)
    word_df: Counter = field(default_factory=Counter)
    name_df: Counter = field(default_factory=Counter)

    @classmethod
    def of(cls, notes, total: int | None = None) -> "Counts":  # noqa: ANN001
        counts = cls(total=total if total is not None else 0)
        n = 0
        for note in notes:
            n += 1
            counts.tag_df.update({t.casefold() for t in note.tags})
            counts.word_df.update(set(tokens(note.text)))
            names, _mid = _names(note.text)
            counts.name_df.update(set(names) | {e.casefold() for e in note.entities})
        if total is None:
            counts.total = n
        return counts

    def rare(self, df: int, share: float, floor: int = RARE_FLOOR) -> bool:
        return df <= max(floor, math.floor(share * max(self.total, 1)))


def strength_word(score: float | None) -> str | None:
    """"strong", "some" or "weak" for a deduced link's score; None for none."""
    if score is None:
        return None
    return "strong" if score >= STRONG_AT else "some" if score >= SOME_AT else "weak"


def is_generic(reason: str | None) -> bool:
    """True for the reason `_deduce_reason` writes, in any of its forms."""
    return bool(reason) and reason.strip().casefold().startswith(GENERIC_PREFIX)


#: A list or checkbox mark leading the line, then every emphasis and code mark
#: wherever it is: a closing `**` kept read "Guide**" in a link (INBOX 1696 d).
_LEAD = re.compile(r"^(?:[#>]+\s*|[-*+]\s+|\d{1,3}[.)]\s+)*(?:\[[ xX]\]\s+)?")
_MARKS = re.compile(r"\*\*|~~|`+|(?:(?<=^)|(?<=\W))__|__(?=\W|$)")
#: A single asterisk is italic only in a pair, so "2 * 3" and "5* stay" keep theirs.
_ITALIC = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]*?\S)\*(?![\w*])")


def title(text: str, limit: int = 30) -> str:
    """A note's name: its heading, else the composer's name for a title-less
    note (its first clause, six words at most, `composer_frame.link_text`), the
    quotes off for the caller to add, clipped. One name on every surface
    (R3-15, L190): a link reason, a Tidy row, a tool label and the Chat list
    say "Dentist said to floss more and…" for the same note."""
    from tessellate.ai import composer_frame  # lazy: this module imports nothing at load

    named = composer_frame.link_text({"content": text or ""}).strip()
    if named in ("“An empty note”", ""):
        return ""
    shown = _ITALIC.sub(r"\1", _MARKS.sub("", _LEAD.sub("", _WIKI.sub(lambda m: m.group(1), named).strip()))).strip().strip("“”").strip()
    if not shown:
        return ""
    return shown if len(shown) <= limit else shown[: limit - 1].rstrip() + "…"


def _mentions(a: PairNote, b: PairNote) -> str | None:
    """"“A” names “B”" when one note links the other or writes its name."""
    for one, other in ((a, b), (b, a)):
        name = title(other.text, limit=200)
        if len(name) < 4:
            continue
        folded = name.casefold()
        wiki = {m.group(1).strip().casefold() for m in _WIKI.finditer(one.text or "")}
        written = len(name.split()) >= 2 and len(name) >= 8 and re.search(
            r"(?<!\w)" + re.escape(folded) + r"(?!\w)", (one.text or "").casefold()
        )
        if folded in wiki or written:
            return f"“{title(one.text)}” names “{title(other.text)}”"
    return None


def _shared_tags(a: PairNote, b: PairNote, counts: Counts) -> str | None:
    spelled = {t.casefold(): t for t in a.tags}
    shared = [spelled[k] for k in spelled if k in {t.casefold() for t in b.tags}]
    shared = [t for t in shared if counts.rare(counts.tag_df.get(t.casefold(), 2), TAG_SHARE)]
    if not shared:
        return None
    shared.sort(key=lambda t: (counts.tag_df.get(t.casefold(), 2), t.casefold()))
    return "both tagged " + ", ".join(f"#{t}" for t in shared[:3])


def _and(things: list[str]) -> str:
    return " and ".join(things) if len(things) <= 2 else f"{things[0]}, {things[1]} and {len(things) - 2} more"


def _name_candidates(a: PairNote, b: PairNote) -> tuple[set[str], dict[str, str]]:
    names_a, mid_a = _names(a.text)
    names_b, mid_b = _names(b.text)
    spelled = {**names_b, **names_a}
    keys = (mid_a & set(names_b)) | (mid_b & set(names_a))
    ents_b = {e.casefold() for e in b.entities}
    for key, shown in {e.casefold(): e for e in a.entities}.items():
        if key in ents_b:
            keys.add(key)
            spelled[key] = shown
    return keys, spelled


def _shared_names(a: PairNote, b: PairNote, counts: Counts, taken: set[str]) -> tuple[str | None, set[str]]:
    keys, spelled = _name_candidates(a, b)
    #: A name that is only a shared tag again ("Launch" beside #launch) adds nothing.
    keys = {
        k for k in keys
        if counts.rare(counts.name_df.get(k, 2), NAME_SHARE) and not (set(tokens(k)) and set(tokens(k)) <= taken)
    }
    # A name inside a longer shared name is the same thing said twice.
    keys = {k for k in keys if not any(k != o and f" {k} " in f" {o} " for o in keys)}
    if not keys:
        return None, set()
    order = sorted(keys, key=lambda k: (counts.name_df.get(k, 2), -len(k.split()), k))[:2]
    words = {w for k in keys for w in tokens(k)}
    return "both mention " + _and([spelled[k] for k in order]), words


def _shared_words(a: PairNote, b: PairNote, counts: Counts, taken: set[str]) -> str | None:
    shared = (set(tokens(a.text)) & set(tokens(b.text))) - taken
    shared = {
        w for w in shared
        if len(w) >= 5 and w not in _PLAIN and w not in _CALENDAR
        and counts.rare(counts.word_df.get(w, 2), WORD_SHARE, WORD_FLOOR)
    }
    if not shared:
        return None
    order = sorted(shared, key=lambda w: (counts.word_df.get(w, 2), w))[:2]
    return "both mention " + _and([f"“{w}”" for w in order])


def _close_in_time(a: PairNote, b: PairNote) -> str | None:
    if not a.category or a.category != b.category or a.category.casefold() == UNCATEGORISED:
        return None
    if a.created_at is None or b.created_at is None:
        return None
    days = abs((a.created_at.date() - b.created_at.date()).days)
    if days > CLOSE_DAYS:
        return None
    when = (
        "the same day" if days == 0 else "a day apart" if days == 1
        else f"{_NUMBER_WORDS[days]} days apart"
    )
    return f"written {when}, both in {a.category}"


def _clues(a: PairNote, b: PairNote, counts: Counts) -> list[str]:
    clues: list[str] = []
    mention = _mentions(a, b)
    if mention:
        clues.append(mention)
    tags = _shared_tags(a, b, counts)
    if tags:
        clues.append(tags)
    taken = {w for t in a.tags if t.casefold() in {x.casefold() for x in b.tags} for w in tokens(t)}
    if len(clues) < 2:
        names, name_words = _shared_names(a, b, counts, taken)
        if names:
            clues.append(names)
        taken |= name_words
    if len(clues) < 2 and not any(c.startswith("both mention") for c in clues):
        words = _shared_words(a, b, counts, taken)
        if words:
            clues.append(words)
    if len(clues) < 2:
        when = _close_in_time(a, b)
        if when:
            clues.append(when)
    return clues


#: The quoted pair's two sentences are cut to this many characters each, so
#: both fit the reason's cap; a cut is marked and is always the line's start.
PAIR_QUOTE = 31
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences(text: str) -> list[str]:
    out = []
    for raw in _SENTENCE_END.split(_WIKI.sub(lambda m: m.group(1), text or "")):
        line = _ITALIC.sub(r"\1", _MARKS.sub("", _LEAD.sub("", raw.strip()))).strip()
        if len(line) >= 12:
            out.append(line)
    return out


def _clip(line: str) -> str:
    line = line.rstrip(".!?")
    if len(line) <= PAIR_QUOTE:
        return line
    return line[:PAIR_QUOTE].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _quoted_pair(a: PairNote, b: PairNote, counts: Counts) -> str | None:
    """The last resort before "similar in meaning": one sentence from each
    note that share at least two plain words, quoted as written (INBOX 725
    g, the composer's own sentence pick). Words most of the notebook uses
    do not count, so a pair is named only for what it shares."""
    def keep(line: str) -> set[str]:
        return {w for w in tokens(line) if w not in _PLAIN and w not in _CALENDAR and not counts.word_df.get(w, 0) > max(RARE_FLOOR, counts.total // 4)}

    best: tuple[int, int, str, str] | None = None
    for sa in _sentences(a.text):
        wa = keep(sa)
        for sb in _sentences(b.text):
            shared = wa & keep(sb)
            if len(shared) < 2:
                continue
            key = (len(shared), -(len(sa) + len(sb)))
            if best is None or key > best[:2]:
                best = (key[0], key[1], sa, sb)
    if best is None:
        return None
    return f"Says “{_clip(best[2])}” and “{_clip(best[3])}”"


def specific_reason(a: PairNote, b: PairNote, counts: Counts) -> str | None:
    """The most specific thing the two notes share, in one sentence, or None
    when all they share is meaning (the caller keeps the generic reason)."""
    clues = _clues(a, b, counts)
    if not clues:
        return _quoted_pair(a, b, counts)
    reason = "; ".join(clues[:2])
    if len(reason) > MAX_CHARS:
        reason = clues[0]
    if len(reason) > MAX_CHARS:
        reason = reason[: MAX_CHARS - 1].rstrip() + "…"
    return reason[0].upper() + reason[1:]
