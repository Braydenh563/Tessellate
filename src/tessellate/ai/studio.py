"""The offline studio's script: an audio overview, or a brief before a meeting, made
from the notes with no model (WORLD_CLASS_PLAN row 35, Q34).

**Only the person's own words.** Every note is told by its name and the first
sentences of its body, shortened with `composer_brief.brief` (a long sentence said by
its gist, never reworded); the only words added are the fixed frame ("Here is an
overview...", "First,", "Next,"). A generator that stitched new sentences from a small
model would put claims in the person's mouth, which an overview of their notebook must
never do. A model may reword the same list later; nothing here needs one.

The result is a list of sentences, so the same list is read on a page, spoken by the
natural voice (`ai/natural_voice.py`, one sentence at a time) and kept as the
transcript lines of the saved recording.
"""

from __future__ import annotations

import re

from tessellate.ai import composer_brief, natural_voice

#: Planning rate for the length asked for. Measured with the shipped voice: 17 words, pauses
#: included, take 5.5 s (about 185 per minute), so 150 leaves the clip under its asked length.
WORDS_PER_MINUTE = 150
LENGTHS = (1, 3, 5)
DEFAULT_MINUTES = 3
#: Most notes in one overview, and how much of one note is read.
MAX_NOTES = 12
PER_NOTE_WORDS = 55
SENTENCE_WORDS = 28
NAME_WORDS = 14

_OPENERS = ("First,", "Next,", "Then,", "After that,", "Also,", "Another one,")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*")
_FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)


def split_note(text: str) -> tuple[str, str]:
    """A note's name (its first line, markdown off, at most `NAME_WORDS` words) and the rest."""
    body = _FRONT.sub("", text or "", count=1).strip()
    first, _, rest = body.partition("\n")
    name = natural_voice.plain(_HEADING.sub("", first)).rstrip(".:;, ")
    words = name.split()
    if len(words) > NAME_WORDS:
        name = " ".join(words[:NAME_WORDS])
    return name, rest.strip()


def _say(sentence: str) -> str:
    """One sentence, shortened to `SENTENCE_WORDS` (a run with no stop is cut at the limit)."""
    said = composer_brief.brief(sentence, SENTENCE_WORDS).rstrip(" .")
    words = said.split()
    if len(words) > SENTENCE_WORDS:
        said = " ".join(words[:SENTENCE_WORDS])
    return said + "."


def _gist(rest: str) -> list[str]:
    """The first sentences of a body that fit `PER_NOTE_WORDS`, each said briefly."""
    out, used = [], 0
    for sentence in natural_voice.sentences(rest):
        said = _say(sentence)
        used += len(said.split())
        if out and used > PER_NOTE_WORDS:
            break
        out.append(said)
        if used >= PER_NOTE_WORDS:
            break
    return out


def _told(text: str) -> tuple[str, list[str]] | None:
    name, rest = split_note(text)
    return (name, _gist(rest)) if name else None


def _lines(index: int, count: int, name: str, gist: list[str]) -> list[str]:
    """One note's sentences: its name behind the opener its place in the telling takes."""
    opener = "Last," if index and index == count - 1 else _OPENERS[index % len(_OPENERS)]
    return [f"{opener} {name}.", *gist]


def _opening(topic: str, brief: bool) -> str:
    topic = " ".join((topic or "").split())[:80]
    if brief:
        return f"Here is a brief about {topic}, from your own notes."
    return f"Here is an overview of your notes about {topic}." if topic else "Here is an overview of your recent notes."


def script(notes: list[dict], *, topic: str = "", minutes: int = DEFAULT_MINUTES, brief: bool = False) -> list[str]:
    """The sentences to read, or [] when no note has anything to say. `notes` are dicts with
    `text`, in the order to read them; the length asked for decides how many are told."""
    budget = max(1, min(minutes, max(LENGTHS))) * WORDS_PER_MINUTE
    told: list[tuple[str, list[str]]] = []
    words = 0
    for note in notes[:MAX_NOTES]:
        found = _told(str(note.get("text") or ""))
        size = len(found[0].split()) + sum(len(line.split()) for line in found[1]) if found else 0
        if found and (not told or words + size <= budget):
            told.append(found)
            words += size
    if not told:
        return []
    body = [line for index, (name, gist) in enumerate(told) for line in _lines(index, len(told), name, gist)]
    close = [f"That was {len(told)} notes."] if len(told) > 1 and not brief else []
    return [_opening(topic, brief), *body, *close]


def as_text(lines: list[str]) -> str:
    """The script as it is read on the page: one paragraph."""
    return " ".join(lines)
