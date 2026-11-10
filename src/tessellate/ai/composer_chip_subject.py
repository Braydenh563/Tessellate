"""The subject a follow-on chip asks about (R9-1): a noun phrase the notes use, or none.

A chip is a button that asks a question back, so a subject built from the
question's leftover words ("with the kitchen", "the plumber's", "hannah allergic")
is a button that asks garbage. The subject is cleaned to what the notes treat as
a thing (a title word, or a word they say after "the", "my", "a"); when it is not
one, the chip is not made.
"""

from __future__ import annotations

import re

from tessellate.ai.composer_ask import _holds, _stem

_LEAD = re.compile(r"^(?:with|the latest on|latest|newest|of|on|about|for|to|and|at|in|by|from|is|are|was|were)\s+", re.I)
_OWNERS = frozenset({"the", "my", "our", "your", "his", "her", "their", "a", "an"})
#: Words that are the question's own, never a thing: asks, verbs and fillers.
_NOT_A_THING = frozenset(
    "latest newest called named due date needs need live lives eat eats born think thought allergic going doing "
    "number phone coming come got have has had like likes love loves want wants say said tell told know".split()
)
_NAME_WORD = re.compile(r"[\w'’&-]+")


def _titles(views: list) -> dict[str, str]:
    return {str(v.title).strip().lower(): str(v.title).strip() for v in views if getattr(v, "titled", False) and v.title}


def _said_as_a_thing(word: str, views: list) -> bool:
    """Whether the notes use `word` as a noun: in a title, or after an article or "my"."""
    if any(word.lower() in {w.lower() for w in str(v.title).split()} for v in views if getattr(v, "titled", False)):
        return True
    pattern = re.compile(rf"\b(?:the|a|an|my|our|your|his|her|their) (?:\w+ )?{re.escape(word)}\b", re.I)
    return any(pattern.search(str(v.note.get("content") or "")) for v in views)


def _split_owner(subject: str) -> tuple[str, list[str]]:
    """The owner word ("my", "the") and the words of the thing, from a chip's leftover span."""
    text = subject.strip()
    while _LEAD.match(text):
        text = _LEAD.sub("", text, count=1)
    words = _NAME_WORD.findall(re.sub(r"['’]s$", "", text).strip())
    owner = words[0].lower() if words and words[0].lower() in _OWNERS else ""
    return owner, (words[1:] if owner else words)


def _plausible(core: list[str], question: str) -> bool:
    """Whether `core` can be a noun phrase: short, no verbs or possessives inside, side by side in the question (R9-1)."""
    if not core or len(core) > 4 or any(w.lower() in _NOT_A_THING or w.lower() in {"with", "latest"} for w in core):
        return False
    if len(core) > 2 and any(w.endswith(("'s", "’s")) for w in core[:-1]):
        return False
    #: Words the question did not put side by side ("Hannah Klara Sun") are no name.
    name = " ".join(core).lower()
    return not (question and len(core) > 1 and not re.search(rf"\b{re.escape(name)}(?:['’]s)?\b", question.lower().replace("-", " ")))


def _owner_as_typed(name: str, question: str) -> str:
    """"the plumber" as typed, not the bare title."""
    said = re.search(rf"\b(the|my|our) {re.escape(name.lower())}\b", question.lower()) if question else None
    return said.group(1) if said else ""


def clean(subject: str, views: list, question: str = "") -> str:
    """`subject` as a chip names it, or "" when it is no noun phrase the notes use."""
    owner, core = _split_owner(subject)
    if not _plausible(core, question):
        return ""
    name = " ".join(core)
    owner = owner or _owner_as_typed(name, question)
    titled = _titles(views).get(name.lower())
    if titled:
        #: A bare name keeps the note's capitals ("Japan"); "the plumber" stays as typed.
        return titled if not owner else f"{owner} {name}"
    if not views:
        return name  # no notes to check it against, so no owner word either
    known = set().union(*(v.title_words | v.filed_words for v in views))
    if not _said_as_a_thing(core[-1], views) and not _holds(_stem(core[-1].lower()), known):
        return ""
    return " ".join(filter(None, [owner, name]))


#: The chip templates that name a subject (`composer_digest._NEXT_ABOUT` and `composer._next_questions`).
_ABOUT = re.compile(
    r"^(?P<head>When did I (?:last )?write about|What(?:'s| is) the latest on|What else have I saved about|What do I know about|Tell me more about) (?P<subject>.+?)\?$"
)


def fix_chip(chip: str, views: list, question: str = "") -> str:
    """`chip` with its subject cleaned, or "" when the subject is no noun phrase the notes use (R9-1)."""
    found = _ABOUT.match(chip)
    if not found:
        return chip
    subject = clean(found.group("subject"), views, question)
    return f"{found.group('head')} {subject}?" if subject else ""
