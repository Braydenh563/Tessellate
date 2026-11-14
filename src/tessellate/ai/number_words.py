"""Numbers spoken in words, one to ninety-nine ("twenty-one", "forty two"), for the
dates utility: "what day is it in twenty-one days" is read as 21."""

from __future__ import annotations

_UNITS = (
    "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
_ONES = _UNITS[:9]

#: The regex source for one such number, longest forms first ("twenty-one" before "twenty").
PATTERN = rf"(?:(?:{'|'.join(_TENS)})(?:[- ](?:{'|'.join(_ONES)}))?|{'|'.join(reversed(_UNITS))})"

_VALUE = {w: i + 1 for i, w in enumerate(_UNITS)} | {w: 20 + 10 * i for i, w in enumerate(_TENS)}


def value(said: str) -> int | None:
    """The number `said` spells ("twenty-one" is 21), or None when it is no such number."""
    parts = said.lower().replace("-", " ").split()
    if not parts or not all(p in _VALUE for p in parts):
        return None
    if len(parts) == 1:
        return _VALUE[parts[0]]
    if len(parts) == 2 and _VALUE[parts[0]] >= 20 and _VALUE[parts[0]] % 10 == 0 and _VALUE[parts[1]] < 10:
        return _VALUE[parts[0]] + _VALUE[parts[1]]
    return None
