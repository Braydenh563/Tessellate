"""A note that is one word, asked for by its name (round 2 E11).

"What is the milk note", "what's in milk" and "what do I know about hi" named a
note whose whole content is its title, and got five different answers (a joke
through a greeting filter, "no luck", "general knowledge"). One word is a
valid note, and the answer says so, in the note's own words.
"""

from __future__ import annotations

import re

_ASK = re.compile(
    r"^(?:what(?:'s|\s+is|\s+are)?\s+(?:in|about)|what\s+do\s+i\s+know\s+about|tell\s+me\s+about|show\s+me|open|what(?:'s|\s+is))\s+(?:the\s+|my\s+)?(?P<name>[^\s]+?)(?P<note>\s+note)?\s*\??$",
    re.I,
)


def named(question: str, notes: list[dict]) -> dict | None:
    """The one-word note `question` names, or None."""
    m = _ASK.match(" ".join(str(question or "").split()))
    if not m:
        return None
    name = m.group("name").strip("“”\"'").lower()
    bare = [n for n in notes if " ".join(str(n.get("content") or "").split()).lower() == name]
    #: "what is hi" is not the note unless the word note is said; the other
    #: openings already name a topic.
    if len(bare) != 1 or (not m.group("note") and re.match(r"^what(?:'s|\s+is)\s+\S+$", question.strip(), re.I)):
        return None
    return bare[0]


def say(note: dict) -> str:
    word = " ".join(str(note.get("content") or "").split())
    #: The quoted name is the word; saying it again after a colon repeated it (L204, E18).
    return f"Your note “{word}” is just that one word."
