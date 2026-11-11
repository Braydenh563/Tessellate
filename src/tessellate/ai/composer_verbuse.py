"""A verb is not the noun it shares a stem with (W7b B10).

"What do I know about books" listed "You need to book the tram" and "book the dentist" as notes
loosely related to books: the stemmer folds book, books and booked. A plural subject names the
things; a note whose only use of the word is a verb ("to book the tram", "Book the dentist",
"booked") is not about them. Pure words, linear (one pass over the tokens)."""

from __future__ import annotations

import re

#: What a verb is read after: "to book", "will book", "please book", "and book".
_BEFORE = frozenset("to will would can could must should shall please let's lets then and gonna i'll we'll never also just".split())
#: What a verb is followed by: "book the tram", "book it", "book for Friday". A noun is followed by "club", "list", "of".
_AFTER = frozenset("the a an my our your his her their this that these those it them us me him for in on at with".split())
_TOKEN = re.compile(r"[A-Za-z']+|[.!?\n]")


#: What a noun is followed by: "book club", "book list", "book of poems", "book is overdue". Opening a line, "Book car
#: service" is the verb and "Book club meets" is not.
_NOUN_AFTER = frozenset("club clubs list lists shelf shelves idea ideas review reviews store shop fair recommendations recommendation of is are was were has had about by title titles".split())


def _verbal(tokens: list[str], at: int) -> bool:
    """Whether the token at `at` is the verb: after a verb-taker, or opening a sentence or a checklist line."""
    after = tokens[at + 1].lower() if at + 1 < len(tokens) else ""
    before = tokens[at - 1].lower() if at else "."
    if before in _BEFORE:
        return after not in _NOUN_AFTER
    return before in ".!?\n" and (after in _AFTER or bool(after) and after not in _NOUN_AFTER and after not in ".!?\n")


def only_a_verb(word: str, text: str) -> bool:
    """Whether `text` uses a plural subject word `word` ("books") only as the verb it shares a stem with.
    False for a singular word, for a text that never writes the word or its forms, and for any noun use."""
    low = (word or "").lower()
    if len(low) < 4 or not low.endswith("s") or low.endswith("ss"):
        return False
    base = low[:-1]
    tokens = _TOKEN.findall(str(text or "")[:20_000])
    seen = False
    for i, token in enumerate(tokens):
        t = token.lower()
        if t == low:
            return False
        if t == base:
            if not _verbal(tokens, i):
                return False
            seen = True
        elif t in (base + "ed", base + "ing", base + "d") and not t.endswith("eed"):
            seen = True
    return seen


def drop(question_words: list[str], scored: list, text_of) -> list:  # noqa: ANN001
    """`scored` ((hits, view) pairs) without the notes that only use a plural subject word as its verb;
    `scored` itself when that would leave none. A note that holds a second word of the question stays."""
    plural = [w for w in question_words if len(w) > 3 and w.lower().endswith("s") and not w.lower().endswith("ss")]
    if not plural:
        return scored
    kept = [(h, v) for h, v in scored if h > 1 or not any(only_a_verb(w, text_of(v)) for w in plural)]
    return kept or scored
