"""A note that shares only an everyday word with the question is not its answer.

"How many vacation days do I have" found the Kyoto note on "day trip": the one
word the question and the note share is a word every notebook holds. When the
notes found match the question on such words alone, and the question also asks
for something none of them holds (a "vacation", a "captain", a "schedule"), the
answer says the notebook holds nothing on it instead of quoting the nearest note.
"""

from __future__ import annotations

import re
from datetime import date

from tessellate.ai import composer, composer_empty, composer_frame
from tessellate.ai.composer_ask import _stem
from tessellate.ai.composer_unfound import _FOREIGN, _INSTRUCTION_STEMS, _MANNER, _NOT_A_NOUN, _SMALL_WORDS, _frame_stems, _seen, _unfound_terms
from tessellate.core.lazyre import lazy_compile

#: Words a notebook holds whatever it is about: matching on these alone is no coverage.
_EVERYDAY = frozenset(
    _stem(w)
    for w in "day days meeting meetings ship mean event events flight flights book books time off week weeks month year thing".split()
)

#: A question about a calendar ("my meeting schedule", "a meeting today") is not answered by a note about a meeting held.
_CALENDAR_CUE = lazy_compile(r"\b(?:schedule|scheduled|agenda|calendar|today|tonight|tomorrow)\b", re.I)


def _everyday_only(terms: list[str], found: set[str], frame: frozenset[str]) -> bool:
    """True when the words the notes match are all everyday ones, and at least one is."""
    covered = [
        t for t in terms
        if len(t) >= 3 and t.lower() not in _SMALL_WORDS and _stem(t) not in frame and _seen(t, found)
        and (_stem(t) in _EVERYDAY or not (_NOT_A_NOUN.search(t) or _stem(t) in _INSTRUCTION_STEMS))
    ]
    return bool(covered) and all(_stem(t) in _EVERYDAY for t in covered)


#: A bare event with a clock time and nothing to do with it: "lunch with my friend at noon today".
_BARE_EVENT = lazy_compile(
    r"^(?!(?:what|when|where|who|why|how|which|is|are|do|does|did|can|could|would|will|should|show|tell|list|find|add|remove|delete|set|make|take|put|remind|cancel|clear|check)\b)"
    r"(?P<what>[a-z][a-z' ]{2,40}?)\s+(?P<when>(?:at|around)\s+(?:noon|midnight|\d{1,2}(?::\d\d)?\s*(?:am|pm)?)(?:\s+(?:today|tonight|tomorrow))?)\W*$",
    re.I,
)


def _bare_event(question: str, found: set[str], terms: list[str]) -> dict | None:
    """An event stated with a time that no note mentions: asked what to do with it, never searched for ("lunch" is in no note)."""
    said = _BARE_EVENT.match(" ".join((question or "").split()))
    if not said or any(_seen(t, found) for t in terms):
        return None
    line = f"What should I do with that? To set a reminder, say it as: remind me about {said.group('what').lower()} {said.group('when').lower()}."
    return {**composer._result([("template", line)], "none"), "answered": True}


def absent(question: str, notes: list[dict], today: date, voice: str) -> dict | None:
    """The "nothing on this" answer, or None when the notes found cover the question."""
    views = composer._note_views(notes)
    if not views:
        return None
    terms = composer._fit_terms(composer.plan(question, today).terms, views)
    found: set[str] = set()
    for view in views:
        found |= view.words | view.title_words | view.filed_words
    if (event := _bare_event(question, found, terms)) is not None:
        return event
    frame = _frame_stems(question)
    if not _everyday_only(terms, found, frame):
        return None
    out = composer._fresh_answer(views, today, None, "", "", voice, question)
    #: What the question asks for that no note holds: a noun, else the calendar word or the verb of doing.
    gone = _unfound_terms(out, terms, views)
    unseen = [t for t in terms if len(t) >= 3 and t.lower() not in _SMALL_WORDS and not _seen(t, found)]
    gone = gone or [t for t in unseen if _stem(t) in frame] or [t for t in unseen if _stem(t) not in _INSTRUCTION_STEMS]
    cue = _CALENDAR_CUE.search(question or "")
    gone = gone or ([cue.group(0).lower()] if cue else [])
    if not gone:
        return None
    return composer_empty._nothing("what", None, voice, [composer_empty._as_typed(w, question) for w in gone[:3]], out)
