"""A name typed one slip off ("hanna" for Hannah) is read as the note's name (R9-14).

The speller changes only words of the dictionary; a name is not in it. The names a notebook writes with a capital
and never without ("Hannah", "Marek") are the vocabulary here, so a common word is never "corrected" into one,
and only a subject word is read (after about, is, of, for, ..., or last)."""

from __future__ import annotations

import re

from tessellate.ai import question_noise

#: A word after one of these (or the last word) can be the subject asked about.
_BEFORE_SUBJECT = frozenset({"about", "is", "of", "for", "on", "does", "did", "was", "with", "from", "to", "who", "whos"})
_CAPITAL = re.compile(r"\b[A-Z][a-z]{3,}\b")
_LOWER = re.compile(r"\b[a-z]{3,}\b")


def names_of(notes: list[dict]) -> frozenset[str]:
    """The names the notes write with a capital and never without, lower case."""
    text = " ".join(f"{n.get('title') or ''} {n.get('content') or ''}" for n in notes or ())
    return frozenset(w.lower() for w in _CAPITAL.findall(text)) - frozenset(_LOWER.findall(text))


def respell(question: str, names: frozenset[str], fixed: list | None = None) -> str:
    """`question` with a subject word that is one slip from one of `names` put right; `fixed` gets
    (typed, chosen) as the speller's repairs do, which is what lets the answer say how it read the question."""
    if not names or not question:
        return question
    tokens = question.split(" ")
    for i, token in enumerate(tokens):
        word = token.strip("?.!,;:").lower()
        last = all(not t.strip("?.!,;:") for t in tokens[i + 1:])
        if len(word) < 4 or not word.isalpha() or word in names or not (last or (i and tokens[i - 1].lower() in _BEFORE_SUBJECT)):
            continue
        chosen = question_noise.nearest(word, names)
        if chosen:
            tokens[i] = token.lower().replace(word, chosen)
            if fixed is not None:
                fixed.append((token, tokens[i]))
    return " ".join(tokens)
