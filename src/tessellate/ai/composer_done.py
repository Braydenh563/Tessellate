"""When a later note records an open checklist line as done (fable-eye F3, F15).

A leaf, so the reading closes no import cycle: composer_quote and
composer_plan ask it from inside the composer, which composer_slots imports
(both used to import composer_slots back, two cycles through the composer).
"""

from __future__ import annotations

import functools
import re
from datetime import date

from tessellate.ai import factgraph
from tessellate.ai.composer_ask import _words


#: How a day is said ("29 October"): the digest's own, bound by
#: `composer_lists.bind` when the digest loads (as `composer_lists._day`).
_day = None


#: A line that says the doing did not happen ("Didn't buy replacement mint").
_UNDONE = re.compile(r"\b(?:did\s*n[o']t|didnt|not|never|forgot|failed|yet\s+to)\b", re.I)


#: Words that carry no subject: the framing of the request itself.
_FILLER = frozenset({
    "the", "a", "an", "my", "our", "on", "for", "to", "of", "in", "at", "with", "list", "lists", "note", "notes", "item", "items",
    "task", "tasks", "checklist", "todo", "still", "do", "i", "we", "it", "that", "this", "yet", "already", "ever", "last",
})


def _stems(text: str) -> list[str]:
    seen: list[str] = []
    for w in _words(text):  # noqa: SLF001  # the composer's own stemmer, so question and note read alike
        if w not in _FILLER and w not in seen:
            seen.append(w)
    return seen


def _holds(sentence, stems: list[str]) -> bool:  # noqa: ANN001
    have = set(_words(sentence.text))  # noqa: SLF001
    return bool(stems) and all(s in have for s in stems)


@functools.lru_cache(maxsize=256)
def _verb_forms(word: str) -> frozenset[str]:
    """Every stem a verb is written as: "pay" is also "paid", "write" is
    "wrote" and "written", so "did I pay the phone bill" meets "Paid the
    phone bill" (audit 1030 Z18)."""
    forms = {word.lower()}
    for lemma, past, participle in factgraph._IRREGULAR:  # noqa: SLF001
        every = {lemma, participle, *past.split()}
        if word.lower() in every:
            forms |= every
    return frozenset(st for f in forms for st in _stems(f))


def _says_verb(sentence, forms: frozenset[str]) -> bool:  # noqa: ANN001
    return not forms or bool(forms & set(_words(sentence.text)))  # noqa: SLF001


def _done_later(views: list, verb: frozenset[str], obj, task_view):  # noqa: ANN001, ANN202
    """A line written no earlier than an open task that says the doing
    ("Renewed my library membership today" beside "[ ] Renew library
    membership"): the box was never ticked, the later note is the record."""
    since = task_view.written
    for view in sorted(views, key=lambda v: v.written or since, reverse=True):
        if since and view.written and view.written < since:
            continue
        for s in view.sentences:
            if s.kind != "task" and _holds(s, obj) and _says_verb(s, verb) and not (_INTENT.search(s.text) or _UNDONE.search(s.text)):
                return view, s
    return None


#: Where an open task's own words stop being the doing ("Renew library
#: membership - due 28 October" is renew + library membership).
_DOING_END = re.compile(r"\s+(?:-|due|by|on|before|at)\b|[,.;:(]", re.I)


def recorded_later(views: list, view, task):  # noqa: ANN001, ANN202
    """(note, sentence) of a later note that records the doing of an open
    checklist line, or None. One item has one state: the open list, the
    yes or no and the reminder offer all ask this (fable-eye F3, F15)."""
    if task.kind != "task" or task.done or not view.written:
        return None
    words = _DOING_END.split(re.sub(r"^\s*[-*]?\s*\[[ xX]\]\s*", "", task.text).strip(), 1)[0].split()
    if len(words) < 2 or not (obj := _stems(_asked_thing(words))):
        return None
    return _done_later([v for v in views if v is not view], _verb_forms(words[0]), obj, view)


def done_later(views: list, view, tasks: list) -> dict[int, tuple]:  # noqa: ANN001
    """`id(task)` to (later note, sentence) for each unticked line of `view`
    a later note records as done: every reader that counts or shows a
    checklist asks this, so a box reads one state everywhere (fable-eye F15)."""
    return {id(t): got for t in tasks if (got := recorded_later(views, view, t))}


#: A line that plans the doing is not a record of it: "did I pay rent"
#: beside "Remember to pay rent on the 1st" is "not yet" (audit 1030 Z19).
_INTENT = re.compile(
    r"^\s*(?:[-*]\s*)?(?:i\s+)?(?:remember to|need to|have to|must|should|plan to|going to|want to|don't forget to|todo:?|to do:?)\b"
    #: "Pay rent, due 10 November" is a to-do with a date, not a payment (round 1 D4).
    r"|\b(?:due|deadline)\b",
    re.I,
)


def _asked_thing(words: list[str]) -> str:
    """"anything about meditation" is meditation."""
    return re.sub(r"^(?:(?:anything|something|much)\s+)?(?:about|on|of|regarding|to|for)\s+", "", " ".join(words[1:]), flags=re.I)


def done_later_note(got: tuple, today: date) -> str:
    """" (done: your note of 29 October says so)", after the item's line."""
    day = got[0].written
    return f" (done: {'your note of ' + _day(day, today) if day else 'one note'} says so)"
