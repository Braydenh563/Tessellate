"""Spelled numbers in a whole question (CHAT_PLAN U17).

"List the twenty notes" and "show me the last two notes" held a number the
rules only read as a digit: `timewords` and `reminder_parser` read "two"
inside a time phrase, and nothing read it anywhere else. `normalise` turns
number words to digits once, ahead of every rule, so each of them sees "20"
and "2". What it leaves alone is as much of the design as what it turns:
quoted text is the person's own words, a capitalised word in the middle of a
sentence is a name ("Five Guys"), and "one" is a pronoun unless a unit or a
note follows it ("which one", "no one").
"""

from __future__ import annotations

import re

from tessellate.entry import timewords

#: `timewords` knows "a", "an", "a couple of" and "few" as counts of a time
#: phrase; here they are ordinary words, so only its plain numbers are kept.
_SMALL = {w: n for w, n in timewords._NUMBER_WORDS.items() if w not in ("a", "an", "few", "couple of")}  # noqa: SLF001
_SMALL.update({"zero": 0, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19})
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}

#: What "one" may count: a pronoun ("the one", "which one") is not changed.
_COUNTED = r"(?:days?|weeks?|months?|years?|hours?|minutes?|notes?|entr(?:y|ies)|items?|tags?|times?|things?)"

_ALL = sorted({*_SMALL, *_TENS}, key=len, reverse=True)
_TENS_ALT = "|".join(sorted(_TENS, key=len, reverse=True))
_UNITS_ALT = "|".join(w for w in sorted(_SMALL, key=len, reverse=True) if 1 <= _SMALL[w] <= 9)
_NUMBER = re.compile(
    rf"\b(?:(?P<tens>{_TENS_ALT})(?:[\s-]+(?P<unit>{_UNITS_ALT}))?|(?P<small>{'|'.join(w for w in _ALL if w not in _TENS)}))\b(?!\s+(?:hundred|thousand|million)\b)",
    re.I,
)
_QUOTED = re.compile(r'"[^"]*"|“[^”]*”|`[^`]*`')
_COUNTED_AFTER = re.compile(rf"\s+{_COUNTED}\b", re.I)


def _digits(match: re.Match, text: str) -> str:
    word = match.group(0)
    starts = match.start() == len(text) - len(text.lstrip())
    #: A capital in the middle of a sentence is a name, not a count.
    if word[0].isupper() and not starts:
        return word
    if match.group("tens"):
        return str(_TENS[match.group("tens").lower()] + (_SMALL[match.group("unit").lower()] if match.group("unit") else 0))
    small = match.group("small").lower()
    if small == "one" and not _COUNTED_AFTER.match(text, match.end()):
        return word
    return str(_SMALL[small])


def _plain(text: str) -> str:
    return _NUMBER.sub(lambda m: _digits(m, text), text)


def normalise(question: str) -> str:
    """`question` with its number words as digits,
    outside anything quoted; the same text when it has none. Ordinals stay
    spelled: every reader of "the second note" takes the word, and "2nd" reads
    as a day of the month to the time rules."""
    text = question or ""
    if not text or not re.search(r"[A-Za-z]", text):
        return text
    out: list[str] = []
    last = 0
    for quoted in _QUOTED.finditer(text):
        out.append(_plain(text[last : quoted.start()]))
        out.append(quoted.group(0))
        last = quoted.end()
    out.append(_plain(text[last:]))
    return "".join(out)
