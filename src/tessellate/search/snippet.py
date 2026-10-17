"""Quoted lines that start and end at a word.

A source card, a search result and a tool's preview show a line of a note.
Cutting it at a character offset began it mid-word ("uding servers") and
ended it mid-word; these two helpers move each cut to the nearest space.
"""

from __future__ import annotations

ELLIPSIS = "…"


def _flat(text: object) -> str:
    return " ".join(str(text or "").split())


def clip_words(text: object, limit: int) -> str:
    """`text` flattened to one line of at most `limit` characters, cut at a
    word with an ellipsis. A single word longer than the limit is cut inside
    it rather than dropped, so a line is never empty."""
    flat = _flat(text)
    if len(flat) <= limit:
        return flat
    cut = flat[: max(1, limit - 1)]
    if flat[len(cut)] != " ":
        space = cut.rfind(" ")
        if space > 0:
            cut = cut[:space]
    return cut.rstrip(" ,;:-") + ELLIPSIS


def window_words(text: object, start: int, width: int) -> str:
    """About `width` characters of `text` from `start`, both ends moved to a
    word. An ellipsis marks a side where the text goes on."""
    flat = _flat(text)
    start = max(0, min(start, len(flat)))
    if start and flat[start - 1] != " ":
        # `start` is inside a word: begin at the next one.
        space = flat.find(" ", start)
        start = len(flat) if space < 0 else space + 1
    end = start + width
    if end < len(flat):
        if flat[end] != " ":
            space = flat.rfind(" ", start, end)
            if space > start:
                end = space
        body = flat[start:end].rstrip(" ,;:-")
        tail = ELLIPSIS
    else:
        body = flat[start:]
        tail = ""
    return (ELLIPSIS if start else "") + body + tail
