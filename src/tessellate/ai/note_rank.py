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

    #: composer_lists.clean, inline: importing it closes a cycle through the plan.
    text = " ".join((question or "").split()).lstrip("\\/'\"` ").rstrip("\\/'\"` ")
    terms = composer.subject_terms(text)
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
