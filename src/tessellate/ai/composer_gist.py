"""The one-line gist on a long note's card, with no model (CHAT_PLAN B22).

A note of a few paragraphs shows its first lines clamped; the gist says what
it is about in under 90 characters, taken from the note's own first sentence
of prose (a heading, a list item or a quoted block is not the gist). Never a
word the note does not hold. A short note returns "": its card shows it whole.
"""

from __future__ import annotations

import re

#: A note shorter than this is read whole on its card; it needs no gist.
MIN_CHARS = 280
#: The line stays under this many characters, the plan's gate ("under 90").
MAX_CHARS = 89

_FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)
_NOT_PROSE = re.compile(r"^\s*(?:#|[-*+]\s|\d+[.)]\s|>|```|!?\[|\|)")


def gist(content: str) -> str:
    """The first sentence of prose, cut to `MAX_CHARS` on a word; "" for a note too short to need one."""
    from tessellate.ai import composer_tidy

    text = _FRONT.sub("", str(content or "").replace("\r\n", "\n"))
    if len(text) < MIN_CHARS:
        return ""
    prose = "\n".join(line for line in text.split("\n") if line.strip() and not _NOT_PROSE.match(line))
    for sentence in composer_tidy.sentences(prose):
        words = sentence.split()
        if len(words) < 4:
            continue
        line = " ".join(words)
        if len(line) <= MAX_CHARS:
            return line
        cut = line[: MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(",;:- ")
        return f"{cut}…"
    return ""
