"""A property of a thing asked for by name ("what is the password for the
bank", "what is his number"): the sentence that holds it leads, and a note
that does not hold it says so ("Your Bank note has no password.") instead of
answering with whatever else it says (audit 1107 round 2, E4, E12, E20).

Closed on purpose: each property is a few words and a shape, so a question
about anything else is left to the ordinary answer."""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\+?\d[\d ()./-]{6,}\d")
_PROPERTIES: dict[str, tuple[re.Pattern, re.Pattern, str]] = {
    #: key: (the question's word, the sentence's word or shape, the noun said)
    "phone": (
        re.compile(r"\b(?:phone|mobile|cell|telephone)\b|\bnumber\b(?!\s+of\b)", re.I),
        re.compile(r"\b(?:phone|mobile|cell|tel|telephone|call)\b", re.I), "phone number"),
    "password": (re.compile(r"\b(?:password|passcode|pin)\b", re.I), re.compile(r"\b(?:password|passcode|pin)\b", re.I), "password"),
    "address": (
        re.compile(r"\baddress\b", re.I),
        re.compile(r"\b(?:address|street|road|avenue|lane|close|drive|postcode|[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})\b", re.I), "address"),
    "email": (re.compile(r"\be-?mail\b(?!\s+(?:me|them|him|her|the)\b)", re.I), re.compile(r"@|\be-?mail\b", re.I), "email address"),
}
#: A "number" that is not a phone number: a count, a reference, a place in a list.
_NOT_PHONE = re.compile(
    r"\b(?:how many|what number|which number|serial|order|house|flat|room|page|reference|booking|account|policy|ticket|"
    r"sort code|item|step|day|week|month|year|line|chapter|lap|set|rep)\b", re.I)


def asked(question: str) -> str:
    """The property `question` asks for, or "" for none."""
    text = " ".join((question or "").split())
    for key, (word, _held, _noun) in _PROPERTIES.items():
        if word.search(text) and not (key == "phone" and _NOT_PHONE.search(text)):
            return key
    return ""


def held(key: str, text: str) -> bool:
    """Whether `text` says the property: its word, or for a phone number a long run of digits."""
    _word, shape, _noun = _PROPERTIES[key]
    if shape.search(text):
        return True
    return key == "phone" and any(len(re.sub(r"\D", "", m.group(0))) >= 8 for m in _DIGITS.finditer(text))


def noun(key: str) -> str:
    return _PROPERTIES[key][2]
