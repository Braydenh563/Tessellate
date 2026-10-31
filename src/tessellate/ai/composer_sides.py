"""The things a comparison names (composer5-1031, the owner's "fix the class").

"Which is the soonest, the dentist, the Lisbon trip or the Tokyo trip" names
three; "compare the dentist with the Lisbon trip in a table" names two and a
wish about the shape of the answer, which is not part of a name. Two readings
live here, both pure text: the format words a side never keeps, and the list of
sides inside the two spans a comparison pattern cuts. `composer.compare_sides`
asks both. Nothing here imports the composer.
"""

from __future__ import annotations

#: The most sides one comparison ranks or heads (the answer stays readable).
MAX_SIDES = 6
MIN_SIDES = 2

_LEADS = ("in", "as", "into", "using", "with")
_ARTICLES = ("a", "an", "the", "")
_ADJECTIVES = ("", "comparison", "simple", "quick", "short", "small", "little", "side by side", "neat", "clear")
_NOUNS = (
    "table", "list", "chart", "grid", "bullets", "bullet points", "bulleted list", "numbered list", "summary", "paragraph",
    "sentence", "sentences", "nutshell", "matrix", "columns",
)
_SUFFIXES = ("", "form", "format")
#: Said alone, at either end of a side.
_ALONE = (
    "side by side", "side-by-side", "for me", "please", "pls", "plz", "thanks", "thank you", "briefly", "quickly",
    "in short", "in brief", "if you can", "if possible", "if you would",
)


def _phrases() -> tuple[tuple[str, ...], ...]:
    found = {tuple(a.split()) for a in _ALONE}
    for lead in _LEADS:
        for article in _ARTICLES:
            for adjective in _ADJECTIVES:
                for noun in _NOUNS:
                    for suffix in _SUFFIXES:
                        found.add(tuple(" ".join(w for w in (lead, article, adjective, noun, suffix) if w).split()))
    #: The longest first, so "in a table form" goes whole, not as "form".
    return tuple(sorted(found, key=len, reverse=True))


_PHRASES = _phrases()
#: What may open a side as well as close it ("in a table, the dentist and the
#: Lisbon trip"); a "with a list ..." at the front is part of a name.
_OPENING = tuple(p for p in _PHRASES if p[0] not in ("with", "using"))


def _plain(word: str) -> str:
    return word.strip(",.;:!?").lower()


def _cut(words: list[str], phrases: tuple[tuple[str, ...], ...], end: bool) -> bool:
    plain = [_plain(w) for w in words]
    for phrase in phrases:
        n = len(phrase)
        if len(words) > n and tuple(plain[-n:] if end else plain[:n]) == phrase:
            if end:
                del words[-n:]
            else:
                del words[:n]
            return True
    return False


def strip_format(side: str) -> str:
    """The side without a format wish or a courtesy at either end: "the Lisbon
    trip in a table, please" is "the Lisbon trip". Word steps, not a pattern
    anchored at the end (CodeQL py/polynomial-redos)."""
    words = side.split()
    while _cut(words, _PHRASES, True) or _cut(words, _OPENING, False):
        pass
    return " ".join(words).strip(" ,")


def _split_words(text: str, joiners: frozenset[str]) -> list[str]:
    """`text` cut at each of the words in `joiners` (and at no other)."""
    parts: list[list[str]] = [[]]
    for word in text.split():
        if _plain(word) in joiners:
            parts.append([])
        else:
            parts[-1].append(word)
    return [" ".join(p) for p in parts]


def _commas(text: str) -> list[str]:
    """"the dentist, the Lisbon trip, and the Tokyo trip" as three pieces: a
    comma cuts, and the "and" or "or" after it goes with the cut."""
    pieces = [p.split() for p in text.split(",")]
    for words in pieces[1:]:
        if len(words) > 1 and _plain(words[0]) in ("and", "or"):
            del words[0]
    return [" ".join(p) for p in pieces]


def listed(raw: str, joiner: str) -> list[str]:
    """The sides one span of a comparison names: cut at commas, and at the
    word that joins the sides when it is "and", "or", "vs" or "versus" (a
    "with" or a "to" joins a side to its partner, never two names in one)."""
    word = joiner.lower().strip(" ,.")
    pieces = _commas(raw)
    if word in ("and", "or", "vs", "versus"):
        pieces = [q for p in pieces for q in _split_words(p, frozenset({word}))]
    return [p.strip(" ,") for p in pieces if p.strip(" ,")]
