"""A question about a link ("why did I link the packing list to the Lisbon
trip", "how are the Lisbon notes connected"): answered from the link table,
the reason the person wrote, never from the notes' bodies (audit 1031 C49).
Parts only; `composer` wraps them as it does every answer."""

from __future__ import annotations

import re

from tessellate.ai import composer_frame, meaning

_ASKS = re.compile(
    r"^(?:why|how|what|which|are|is|did|do|does|show|tell)\b.*\b(?:links?|linked|linking|connect(?:s|ed|ion|ions)?|related|relationship)\b", re.I)
#: "how do I link two notes" is a how-to, which the help register answers.
_HOW_TO = re.compile(r"\bhow (?:do|can|could|should|would|to)\b|\bhow-to\b", re.I)
_NOT_SUBJECT = frozenset(
    "why how what which are is did do does show tell me the a an of to and with between i my you your link links linked linking "
    "connect connects connected connection connections related relationship together notes note".split())
LINKS_MAX = 3


def asks_about_links(question: str) -> bool:
    text = " ".join((question or "").split())
    return bool(_ASKS.match(text)) and not _HOW_TO.search(text)


def _name_stems(note: dict) -> set[str]:
    first = next((ln for ln in str(note.get("content") or "").splitlines() if ln.strip()), "").lstrip("# ").strip()
    words = [*meaning.words_of(first), *meaning.words_of(str(note.get("category") or "")),
             *(w for t in (note.get("tags") or []) for w in meaning.words_of(str(t)))]
    return {meaning.stem(w) for w in words}


def _asked_stems(question: str) -> set[str]:
    return {meaning.stem(w) for w in meaning.words_of(question) if w not in _NOT_SUBJECT}


def _pairs(notes: list[dict]) -> list[tuple[dict, dict, str]]:
    by_id = {n["id"]: n for n in notes}
    seen: set[tuple[int, int]] = set()
    out = []
    for note in notes:
        for other, reason in (note.get("link_reasons") or {}).items():
            key = tuple(sorted((note["id"], int(other))))
            if int(other) in by_id and key not in seen:
                seen.add(key)
                out.append((note, by_id[int(other)], reason))
    return out


def link_line(first: dict, second: dict, reason: str) -> list[tuple]:
    """"You linked A to B: why.", as parts."""
    tail = f": {composer_frame.reason_said(reason)}." if reason else ", and wrote no reason for it."
    return [("template", "You linked "), ("title", composer_frame.short_name(first), first["id"]), ("template", " to "),
            ("title", composer_frame.short_name(second), second["id"]), ("template", tail)]


def answer_parts(question: str, notes: list[dict]) -> list[tuple]:
    """The parts of the answer, or [] when the question asks nothing of a link
    or no two notes it names are linked."""
    if not asks_about_links(question):
        return []
    asked = _asked_stems(question)
    if not asked:
        return []
    ranked = []
    for first, second, reason in _pairs(notes):
        a, b = asked & _name_stems(first), asked & _name_stems(second)
        if a and b:
            ranked.append((len(a) + len(b), first, second, reason))
    ranked.sort(key=lambda row: -row[0])
    parts: list[tuple] = []
    for _, first, second, reason in ranked[:LINKS_MAX]:
        parts += ([("template", " ")] if parts else []) + link_line(first, second, reason)
    return parts
