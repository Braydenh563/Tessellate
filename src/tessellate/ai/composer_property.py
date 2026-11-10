"""A property of a thing asked for by name ("what is the password for the
bank", "what is his number"): the sentence that holds it leads, and a note
that does not hold it says so ("Your Bank note has no password.") instead of
answering with whatever else it says (audit 1107 round 2, E4, E12, E20).

Closed on purpose: each property is a few words and a shape, so a question
about anything else is left to the ordinary answer."""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\+?\d[\d ()./-]{6,}\d")
_PROPERTIES: dict[str, tuple[re.Pattern, re.Pattern | str, str]] = {
    #: key: (the question's word, the sentence's word or shape, the noun said)
    "phone": (
        # "phone" alone is a thing ("when did I get my phone", "cell respiration"): only a "what is X's phone"
        # ask or one that says number is a number ask (PR 216 CI, 3.11). A bare "number" is a phone
        # only beside a person or a business ("Sara's number", "the number for the dentist"), not
        # "what is the number" or "the table number" (round 3, R3-2). "Number of" and "number to" are a
        # count or an action ("number of mice", "the number to call"), never a person's.
        re.compile(
            r"\b(?:his|her|their|my|your|our)\s+(?:phone\s+|mobile\s+|cell\s+)?number\b"
            r"|\w['\u2019]s?\s+(?:phone\s+|mobile\s+|cell\s+)?number\b|\bnumber\s+for\s+(?!(?:the\s+)?day\b)\w"
            r"|\b(?:phone|mobile|cell|telephone)\s+(?:number|no)\b"
            r"|^(?:the\s+)?[a-z]+\s+number\s*[?.!]*$"
            r"|^(?:what(?:'s|s| is| are)?|give me|tell me|find)\b[^?]*\b(?:phone|mobile|cell|telephone)\s*[?.!]*$", re.I),
        re.compile(r"\b(?:phone|mobile|tel|telephone)\b", re.I), "phone number"),
    "password": (re.compile(r"\b(?:password|passcode|pin)\b", re.I), re.compile(r"\b(?:password|passcode|pin)\b", re.I), "password"),
    "address": (
        re.compile(r"\baddress\b", re.I),
        re.compile(r"\b(?:address|street|road|avenue|lane|close|drive|postcode|[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})\b", re.I), "address"),
    "email": (re.compile(r"\be-?mail\b(?!\s+(?:me|them|him|her|the)\b)", re.I), re.compile(r"@|\be-?mail\b", re.I), "email address"),
}
#: The things that carry a number a note may or may not give ("what is the table number": a dinner
#: booking with no table in it is no answer, R3-2 residue). Each is a property of its own word.
NUMBERED = ("table", "room", "seat", "booking", "reservation", "confirmation", "reference", "flight", "order", "account", "policy",
            "ticket", "locker", "gate", "platform", "passport", "visa", "student", "employee", "customer", "parcel", "house", "flat", "apartment", "membership", "licence", "license", "plate", "case", "invoice", "tracking")
for _word in NUMBERED:
    _PROPERTIES[_word] = (
        re.compile(rf"\b{_word}\s+(?:number|no\.?|num|#)(?!\w)", re.I),
        #: The shape is a string, compiled on first use by `held` (through re's own cache):
        #: 25 of them compiled at import cost the composer's cold-import budget (PR 216 CI, 3.12).
        rf"\b{_word}s?\s*(?:number|no\.?|num|ref(?:erence)?|code|id)?\s*[:#-]?\s*(?=[A-Za-z-]*\d)[\w-]+", f"{_word} number")
#: A "number" that is not a phone number: a count, a reference, a place in a list.
_NOT_PHONE = re.compile(
    r"\b(?:how many|what number|which number|serial|order|house|flat|room|page|reference|booking|account|policy|ticket|"
    r"sort code|item|step|day|week|month|year|line|chapter|lap|set|rep|table|seat|car|bus|size|shoe|plate|locker|bin|"
    r"lucky|favourite|favorite|pin)\b|\bnumber\s+of\s+(?:the\s+|my\s+)?\w+s\b", re.I)


#: Only the tail is a pattern: the one or two words before it are read backwards (`_words_before`), so
#: no match can start at every letter of a long run (CodeQL 2097, polynomial ReDoS).
_POSSESSIVE = re.compile(r"['\u2019]s?\s+(?:phone\s+|mobile\s+|cell\s+)?number\b", re.I)
_HAS_PHONE = re.compile(r"^(?:does|did|do)\s+([^?.!]{1,40}?)\s+(?:have|got)\s+(?:a|an|any)\s+(?:phone|mobile|cell)\b", re.I)
_OF_SUBJECT = re.compile(r"\bnumber\s+for\s+([^?.!]{1,60})", re.I)
_LEAD_WORDS = frozenset(("what", "whats", "what's", "is", "are", "give", "me", "tell", "find", "and", "also", "then"))


def _word_at(text: str, end: int) -> int:
    """Where the word ending at `end` starts (a letter, then letters, digits, "_" or "-"), or -1."""
    i = end
    while i > 0 and (text[i - 1].isalnum() or text[i - 1] in "_-"):
        i -= 1
    while i < end and not ("a" <= text[i].lower() <= "z"):
        i += 1
    if i == end or (i > 0 and (text[i - 1].isalnum() or text[i - 1] in "_'\u2019")):
        return -1
    return i


def _words_before(text: str, end: int) -> list[str]:
    """The one or two words that end at `end` (the owner of "Sara's number"), or [] for none."""
    one = _word_at(text, end)
    if one < 0:
        return []
    gap = one
    while gap > 0 and text[gap - 1].isspace():
        gap -= 1
    two = _word_at(text, gap) if gap < one else -1
    return text[(two if two >= 0 else one):end].split()


def subject(question: str) -> str:
    """Whose number is asked for, as the person wrote it ("Sara", "the dentist"); "" for a pronoun or none."""
    text = " ".join((question or "").split())
    words = next(filter(None, (_words_before(text, hit.start()) for hit in _POSSESSIVE.finditer(text))), [])
    if words:
        while words and words[0].lower() in _LEAD_WORDS:
            words.pop(0)
        return " ".join(words)
    hit = _OF_SUBJECT.search(text) or _HAS_PHONE.match(text)
    return hit.group(1).strip() if hit else ""


def asked(question: str) -> str:
    """The property `question` asks for, or "" for none."""
    text = " ".join((question or "").split())
    #: A numbered thing named outright ("passport number") is that thing's number, never a bare-"number" phone ask.
    for key in NUMBERED:
        if _PROPERTIES[key][0].search(text):
            return key
    for key, (word, _held, _noun) in _PROPERTIES.items():
        if word.search(text) and not (key == "phone" and _NOT_PHONE.search(text)):
            return key
    return ""


def held(key: str, text: str) -> bool:
    """Whether `text` says the property: its word, or for a phone number a long run of digits."""
    _word, shape, _noun = _PROPERTIES[key]
    if (re.search(shape, text, re.I) if isinstance(shape, str) else shape.search(text)):
        return True
    return key == "phone" and any(len(re.sub(r"\D", "", m.group(0))) >= 8 for m in _DIGITS.finditer(text))


def noun(key: str) -> str:
    return _PROPERTIES[key][2]


def none_given(question: str, notes: list[dict]) -> str:
    """"None of your notes give a table number." for a numbered thing asked by its noun when no
    note in `notes` says one; "" when the question is no such ask or some note does."""
    key = asked(question)
    if key not in NUMBERED or any(held(key, str(n.get("content") or "")) for n in notes or []):
        return ""
    return f"None of your notes give a {noun(key)}."
