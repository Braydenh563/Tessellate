"""What a "latest ... about X" request asks for (audit 1029 C31): how many
notes and the subject. Pure words, no imports from the composer, so search
can read it without the composer cycle (`tests/test_no_import_cycles.py`)."""

from __future__ import annotations

import re

_NEWEST = frozenset({"last", "latest", "newest", "recent"})
#: The other end of the order: "my 3 oldest baking notes". "first" is one only
#: beside a count ("my first 2 baking notes"); alone it names a note's place.
_OLDEST = frozenset({"oldest", "earliest"})
_NOUNS = frozenset({"note", "notes", "entry", "entries", "thing", "things", "one", "ones", "page", "pages"})
_PLURAL = frozenset({"notes", "entries", "things", "ones", "pages"})
_MARKS = frozenset({"about", "on", "regarding", "concerning", "mentioning", "re", "for", "with", "around"})
_FILLER = frozenset({
    "i", "ive", "have", "had", "wrote", "write", "written", "saved", "save", "added", "add", "made", "make", "typed",
    "jotted", "noted", "took", "taken", "put", "me", "my", "the", "a", "an", "all", "of", "that", "which", "any", "to",
    "show", "what", "is", "was", "were", "are", "did", "do", "does", "please", "can", "you", "tell", "give", "list", "most",
})
_COUNTS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "few": 3,
}
#: "last week", "last night": a time window, not an order.
_TIME_AFTER = frozenset({
    "week", "weeks", "month", "months", "year", "years", "night", "nights", "weekend", "day", "days", "time", "times",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "summer", "winter", "spring", "autumn",
})
_DEFAULT_MANY = 5
_WORD = re.compile(r"[a-z0-9']+")


class Recent:
    """What a "latest ... about X" request asks for: how many notes and the subject (may be empty)."""

    __slots__ = ("count", "oldest", "said_count", "subject")

    def __init__(self, count: int, subject: str, said_count: bool, oldest: bool = False) -> None:
        self.count, self.subject, self.said_count, self.oldest = count, subject, said_count, oldest


def _is_count(word: str) -> bool:
    return word in _COUNTS or (word.isdigit() and 0 < int(word) < 1000)


def _order_word(words: list[str]) -> int:
    """Where the word that orders the notes sits, -1 for none."""
    for i, w in enumerate(words):
        if w in _NEWEST or w in _OLDEST or (w == "first" and i + 1 < len(words) and _is_count(words[i + 1])):
            return i
    return -1


def _after_newest(words: list[str]) -> tuple[int, list[str]] | None:
    """Where the order word sits and the words after it, with a count said
    before it ("my 2 latest notes") moved after it; None for no such word or
    a time window ("last week")."""
    at = _order_word(words)
    if at < 0 or (at + 1 < len(words) and words[at + 1] in _TIME_AFTER):
        return None
    rest = words[at + 1:]
    before = words[:at - 1] if at and words[at - 1] == "most" else words[:at]
    if before and _is_count(before[-1]) and not (rest and _is_count(rest[0])):
        rest = [before[-1], *rest]
    return at, rest


def _leading_count(rest: list[str]) -> tuple[int, list[str]]:
    if rest and (rest[0] in _COUNTS or (rest[0].isdigit() and 0 < int(rest[0]) < 1000)):
        return (int(rest[0]) if rest[0].isdigit() else _COUNTS[rest[0]]), rest[1:]
    return 0, rest


def _subject_of(rest: list[str]) -> str:
    marks = [i for i, w in enumerate(rest) if w in _MARKS]
    tail = rest[marks[-1] + 1:] if marks else [w for w in rest if w not in _NOUNS and w not in _FILLER]
    return " ".join(w for w in tail if w not in {"the", "my", "a", "an", "all"} and w not in _NOUNS).strip()


def recency(text: str, *, bare: bool = False) -> Recent | None:
    """"latest notes about running", "what is the last thing I wrote about
    Atlas", "my last three notes": how many and about what. None when the
    text is no such request, or (unless `bare`) asks for the newest notes with
    no subject and no count, which the newest-notes reader already answers.
    `bare` reads the topic of a find ("latest", "last three"), whose noun the
    command parser already dropped."""
    words = _WORD.findall((text or "").lower()[:300])[:60]
    found = _after_newest(words)
    if found is None:
        return None
    at, rest = found
    count, rest = _leading_count(rest)
    noun = next((w for w in rest[:3] if w in _NOUNS), "")
    if not noun and not (bare and at == 0):
        return None
    subject = _subject_of(rest)
    if not subject and not count and not bare:
        return None
    return Recent(count or (_DEFAULT_MANY if noun in _PLURAL else 1), subject, bool(count), words[at] in _OLDEST or words[at] == "first")


#: "What's the latest on uni", "the newest about my flat", "most recent update
#: on the sync rewrite": the latest on a subject, with no noun for a note.
_LATEST_WORDS = frozenset({"latest", "newest", "recent"})
_UPDATE_NOUNS = frozenset({"news", "update", "updates", "word", "info", "information", "development", "developments"})


#: The same status ask worded without "latest": "what's new with uni", "any
#: news on Lisbon", "where am I with the thesis".
_NEWS = re.compile(r"\b(?:what(?:'s|s| s| is) new|news|where am i(?: at)?) (?:with|on|about) (.+)$")


def status_subject(text: str) -> str:
    """The subject of a "what's the latest on X" question; empty for any other.
    Every note on X is the pool (the newest leads the answer), so the notes
    the search happened to rank first never decide which is the latest."""
    words = _WORD.findall((text or "").lower()[:300])[:60]
    at = next((i for i, w in enumerate(words) if w in _LATEST_WORDS), -1)
    if at < 0 or "most" in words[:at - 1]:
        found = _NEWS.search(" ".join(words))
        return _status_rest(["on", *found.group(1).split()]) if found else ""
    return _status_rest(words[at + 1:])


def _status_rest(rest: list[str]) -> str:
    """The subject after "latest": past any "news" or "update", after its
    "on" or "about", never a time or a lone note noun."""
    while rest and rest[0] in _UPDATE_NOUNS:
        rest = rest[1:]
    if not rest or rest[0] not in _MARKS or any(w in _NOUNS for w in rest[:1]) or (len(rest) > 1 and rest[1] in _TIME_AFTER):
        return ""
    return _status_named([w for w in rest[1:] if w not in {"the", "my", "a", "an", "all", "our"}])


def _status_named(subject: list[str]) -> str:
    if not subject or subject[0] in {"last", "this", "next", "yesterday", "today", "it", "that", "this"}:
        return ""  # a time, not a subject
    return "" if subject[0] in _NOUNS and len(subject) == 1 else " ".join(subject)
