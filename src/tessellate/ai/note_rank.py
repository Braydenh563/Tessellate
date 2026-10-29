"""One ranker for the notes a subject names (audit 1029 C19, C20, C36).

Ask lists them by match count and recency, Chat by retrieval relevance, so the
note that defines a subject ("Sourdough starter") came third in one and last
in the other, and "the garden" put three test notes ahead of the note titled
"Garden". Every shape that lists, opens, summarises or compares notes about a
subject now orders them here, with no model:

1. a note whose title is the subject ("Garden" for "the garden note");
2. a note that defines it in its opening sentences ("Sourdough is a bread ...");
3. a note whose title holds every word of the subject, the shortest title
   first ("Budget 2026" before "Budget check in October");
4. the rest, in the order retrieval gave them.

Within a tier the order given is kept, so the ranker only moves a note
ahead of ones it beats. Works on a note dict or an `Entry` alike. Regexes
here join escaped words with one fixed separator, so they stay linear on long
questions (CodeQL; `tests/test_composer_regex_linear_1029.py`).
"""

from __future__ import annotations

import re
from typing import Any

#: Words that frame the request and are not what it is about.
_FRAME = frozenset({
    "open", "show", "main", "everything", "all", "latest", "last", "newest", "recent", "note", "notes",
    "page", "pages", "entry", "entries", "summary", "summarise", "summarize", "list", "find", "pull", "up",
    "about", "mine", "me", "my", "the",
})
_MAX_TERMS = 6


def _content(note: Any) -> str:
    if isinstance(note, dict):
        return str(note.get("content") or "")
    return str(getattr(note, "content", "") or "")


def subject(question: str) -> list[str]:
    """The words the request is about, as typed, lower-cased: its subject
    terms without the framing words ("open", "main", "notes")."""
    from tessellate.ai import composer
    from tessellate.ai.composer_lists import clean

    terms = composer.subject_terms(clean(question or ""))
    kept = [t.lower() for t in terms if t.lower() not in _FRAME]
    return kept[:_MAX_TERMS]


def stems_of(text: str) -> list[str]:
    """The stems of a request's subject words, as `key` takes them."""
    return _stems(subject(text))


def _stems(words: list[str]) -> list[str]:
    from tessellate.ai import composer

    return [composer._stem(w) for w in words]  # noqa: SLF001  # the composer's own stemmer, so both read words alike


def _defines(subject_words: list[str], content: str) -> bool:
    """Whether a sentence in the note's first lines says what the subject is
    ("Sourdough is ...", "The sourdough starter means ...")."""
    from tessellate.ai import composer

    if not subject_words:
        return False
    said = re.compile(r"^(?:the\s+|a\s+|an\s+)?" + r"\s+".join(re.escape(w) for w in subject_words) + r"\s+(?:is|are|means|refers to)\b", re.I)
    title, start = composer._title(content)  # noqa: SLF001
    body = content[start:] if start else content
    lines = [ln.strip(" \t-*#>") for ln in body.splitlines() if ln.strip()]
    for line in lines[:2]:
        for sentence in re.split(r"(?<=[.!?])\s", line)[:2]:
            if said.match(sentence):
                return True
    return False


def key(note: Any, subject_words: list[str], stems: list[str]) -> tuple[int, int]:
    """The note's tier (0 best) and, inside the title tier, its extra words."""
    from tessellate.ai import composer

    content = _content(note)
    title = composer._title(content)[0]  # noqa: SLF001
    title_stems = _stems([w.lower() for w in re.findall(r"[A-Za-z0-9']+", title)])
    wanted = set(stems)
    if wanted and set(title_stems) - {_stems(["note"])[0]} == wanted:
        return 0, 0
    if _defines(subject_words, content):
        return 1, 0
    if wanted and wanted <= set(title_stems):
        return 2, len(title_stems) - len(wanted)
    return 3, 0


def _written(note: Any) -> float:
    """When the note was made, as a sortable number (0 when unknown)."""
    from datetime import datetime

    value = note.get("created_at") if isinstance(note, dict) else getattr(note, "created_at", None)
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return 0.0
    try:
        return value.timestamp() if value is not None else 0.0
    except (AttributeError, OverflowError, OSError, ValueError):
        return 0.0


def lead(notes: list, question: str) -> list:
    """The notes with the ones that are most plainly about the subject
    first; the same list when the question names no subject."""
    words = subject(question)
    if not words or len(notes) < 2:
        return list(notes)
    stems = _stems(words)
    keyed = [(key(n, words, stems), i, n) for i, n in enumerate(notes)]
    #: Inside a title tier the newest leads, so Ask and Chat agree whatever
    #: order they were handed; the rest keeps the order retrieval gave.
    keyed.sort(key=lambda k: (k[0], -_written(k[2]) if k[0][0] < 3 else 0.0, k[1]))
    return [n for _, _, n in keyed]


# --- "latest about X": filter by the subject, then sort by date (C31) ---------------

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


def recency(text: str, *, bare: bool = False) -> Recent | None:
    """"latest notes about running", "what is the last thing I wrote about
    Atlas", "my last three notes": how many and about what. None when the
    text is no such request, or (unless `bare`) asks for the newest notes with
    no subject and no count, which the newest-notes reader already answers.
    `bare` reads the topic of a find ("latest", "last three"), whose noun the
    command parser already dropped."""
    words = _WORD.findall((text or "").lower()[:300])[:60]
    at = next((i for i, w in enumerate(words) if w in _NEWEST), -1)
    if at < 0 or (at + 1 < len(words) and words[at + 1] in _TIME_AFTER):
        return None
    rest = words[at + 1:]
    count = 0
    if rest and (rest[0] in _COUNTS or (rest[0].isdigit() and 0 < int(rest[0]) < 1000)):
        count = int(rest[0]) if rest[0].isdigit() else _COUNTS[rest[0]]
        rest = rest[1:]
    noun = next((w for w in rest[:3] if w in _NOUNS), "")
    if not noun and not (bare and at == 0):
        return None
    marks = [i for i, w in enumerate(rest) if w in _MARKS]
    tail = rest[marks[-1] + 1:] if marks else [w for w in rest if w not in _NOUNS and w not in _FILLER]
    subject = " ".join(w for w in tail if w not in {"the", "my", "a", "an", "all"} and w not in _NOUNS).strip()
    if not subject and not count and not bare:
        return None
    return Recent(count or (_DEFAULT_MANY if noun in _PLURAL else 1), subject, bool(count))
