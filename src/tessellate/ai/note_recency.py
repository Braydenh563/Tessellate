"""What a "latest ... about X" request asks for (audit 1029 C31): how many
notes and the subject. Pure words, no imports from the composer, so search
can read it without the composer cycle (`tests/test_no_import_cycles.py`)."""

from __future__ import annotations

import re

_NEWEST = frozenset({"last", "latest", "newest", "recent"})
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

    __slots__ = ("count", "said_count", "subject")

    def __init__(self, count: int, subject: str, said_count: bool) -> None:
        self.count, self.subject, self.said_count = count, subject, said_count


def _after_newest(words: list[str]) -> tuple[int, list[str]] | None:
    """Where the newest-word sits and the words after it; None for no such word
    or a time window ("last week")."""
    at = next((i for i, w in enumerate(words) if w in _NEWEST), -1)
    if at < 0 or (at + 1 < len(words) and words[at + 1] in _TIME_AFTER):
        return None
    return at, words[at + 1:]


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
    return Recent(count or (_DEFAULT_MANY if noun in _PLURAL else 1), subject, bool(count))
