"""What a free find searches for (B27): "find notes similar to my dentist one you know"
is a search for "dentist", not for the whole sentence.

The words around the topic say how to look ("similar to", "like", "one") or are
filler ("you know", "or something", "please"); none of them is in the notes."""

from __future__ import annotations

import re

_LIKE = re.compile(r"^(?:(?:that |which |the )?(?:are |is )?(?:very |kinda |kind of |a bit |somewhat )?(?:similar|close|related|like|akin|near|comparable)(?: (?:to|with))?|such as|like)\s+", re.I)
_TRAIL = re.compile(
    r"(?:[\s,]+(?:you know|ya know|y'know|or something|or so|i think|i guess|i mean|please|pls|plz|thanks|thx|for me|right|ok|okay|yeah))+[?.!\s]*$", re.I
)
_HEAD = re.compile(r"^(?:any |all |some )?(?:notes?|entries|stuff|things?)\s+(?:that (?:are|is) )?", re.I)
_ONE = re.compile(r"\s+(?:ones?|notes?|entry|entries|stuff|things?)$", re.I)
_OWNER = re.compile(r"^(?:my|the|our|your|that|this)\s+", re.I)


def topic(said: str) -> str:
    """`said` as the words to search for: the likeness, the trailing "one" and the filler off.
    A topic that is only those words is returned unchanged, so a search never goes empty."""
    text = _HEAD.sub("", _TRAIL.sub("", said.strip()).strip(), count=1)
    if not _LIKE.match(text):
        return said
    stripped = _OWNER.sub("", _LIKE.sub("", text, count=1).strip(), count=1)
    stripped = _ONE.sub("", stripped).strip(" ,.?!")
    return stripped or said
