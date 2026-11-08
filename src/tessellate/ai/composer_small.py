"""Three small questions the composer answers in a sentence, with no model
(CHAT_PLAN U16, A22 and A24): a what-if, "where did I write X" and "show me
something old".

Each reads only the notes the route handed over, quotes them through the same
`_Answer` the rest of the composer uses (so every quote has its grounding
row), and returns None when the question is not its kind or the notes cannot
answer it, which leaves the ordinary path to answer as before.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from tessellate.ai import realise
from tessellate.ai.composer_answer import _Answer
from tessellate.ai.composer_ask import _holds, _stem, _words, subject_terms, user_today
from tessellate.ai.composer_help import _result
from tessellate.ai.composer_read import NoteView, read_note

# --- U16: a what-if has no fact to answer from ----------------------------------------

_WHAT_IF = re.compile(
    r"^\s*(?:(?:ok|okay|so|hmm|and)[,\s]+)?(?:what (?:if|would happen if|will happen if|happens if|might happen if|could happen if)"
    r"|suppose(?: that)?|supposing(?: that)?|imagine(?: that)?|let'?s say|how would (?:it|things) (?:be|change) if)\s+(?P<premise>.+?)\s*[?.!]*\s*$",
    re.I,
)

#: The verbs a premise is made of, which are not what the notes would hold
#: ("move" in "what if I move to Lisbon"): the subject is what is left.
_PREMISE_VERBS = frozenset(
    "move moved moving go going went stop stopped stopping start started starting quit quitting leave left leaving take took taking "
    "get got getting buy bought buying sell sold selling change changed changing try tried trying lose lost losing "
    "give gave giving make made making do did doing keep kept keeping join joined joining become became".split()
)
_PREMISE_FILLER = frozenset({"i", "we", "my", "the", "a", "an", "to", "of", "up", "out", "off", "on", "in", "at", "for", "with", "it", "that", "not", "never"})

NO_FACT = "Your notes do not say what would happen."
MAX_QUOTES = 2


def _subject_words(premise: str) -> list[str]:
    """The premise's subject words as the person typed them ("Lisbon", not "lisbon")."""
    typed = {w.lower(): w for w in re.findall(r"[\w'-]+", premise)}
    return [typed.get(t.lower(), t) for t in subject_terms(premise) if t.lower() not in _PREMISE_VERBS and t.lower() not in _PREMISE_FILLER]


def _views(notes: list[dict]) -> list[NoteView]:
    return [v for v in (read_note(n, i) for i, n in enumerate(notes or [])) if v]


def _holding(view: NoteView, stems: set[str]) -> int:
    return sum(1 for st in stems if _holds(st, view.words))


def _spoken(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _quotes_for(view: NoteView, stems: set[str]) -> list:
    """The sentences of `view` that say the subject, best first, in the note's order."""
    quotes = sorted((s for s in view.sentences if any(_holds(st, set(_words(s.text))) for st in stems)),
                    key=lambda s: (-sum(1 for st in stems if _holds(st, set(_words(s.text)))), s.order))[:MAX_QUOTES]
    #: A note filed under the subject (titled "Gym plan") that never says the
    #: word in a sentence is quoted from its start: what it holds is still on it.
    quotes = quotes or [s for s in view.sentences if s.kind in ("prose", "item", "task")][:MAX_QUOTES]
    return sorted(quotes, key=lambda s: s.order)


def what_if(question: str, notes: list[dict], *, today: date | None = None) -> dict | None:
    """What the notes hold about a what-if's subject, then the line that says
    they do not say what would happen. A consequence is never stated: the
    answer only quotes, so nothing in it is a claim the notes did not make."""
    found = _WHAT_IF.match(question or "")
    if not found:
        return None
    words = _subject_words(found.group("premise"))
    stems = {_stem(w) for w in words}
    views = _views(notes)
    held = sorted((v for v in views if stems and _holding(v, stems)), key=lambda v: (-_holding(v, stems), v.rank))
    out = _Answer({v.id: v for v in views}, today or user_today())
    if not held:
        subject = f"about {_spoken(words)}" if words else "on that"
        out.parts.append(("template", f"Your notes hold nothing {subject}, and they do not say what would happen."))
        return _result(out.parts, "what")
    view = held[0]
    quotes = _quotes_for(view, stems)
    if not quotes:
        return None
    out.parts.append(("template", f"Your notes say this about {_spoken(words)}: "))
    for i, sentence in enumerate(quotes):
        if i:
            out.parts.append(("template", " "))
        out.q(sentence, words)
    out.cite(view)
    out.parts.append(("template", f" {NO_FACT}"))
    return _result(out.parts, "what", out.rows)


# --- A22: where did I write X ---------------------------------------------------------

_WHERE = re.compile(
    r"^\s*where (?:did|have|had|do) (?:i|we) (?:write|wrote|written|put|note|noted|jot|jotted|save|saved|store|stored|keep|kept|mention|mentioned|say|said|record|recorded|type|typed)"
    r"(?:\s+down)?\s+(?P<rest>.+?)\s*[?.!]*\s*$",
    re.I,
)
_FILLER = re.compile(r"^(?:(?:about|on|that|the|my|it|of)\s+)+", re.I)
_HEADING = re.compile(r"^#{2,6}[ \t]+(.+?)[ \t#]*$", re.M)
_EDITED = re.compile(r"edited\s+\w+\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
_MONTHS = {m: i for i, m in enumerate("january february march april may june july august september october november december".split(), 1)}


def _edited_day(note: dict) -> date | None:
    """The day the note was last edited, from the route's `written` words
    ("Wednesday 23 September 2026, 09:40, edited Friday 25 September 2026,
    11:02"), else None."""
    found = _EDITED.search(str(note.get("written") or ""))
    if not found or found.group(2).lower() not in _MONTHS:
        return None
    try:
        return date(int(found.group(3)), _MONTHS[found.group(2).lower()], int(found.group(1)))
    except ValueError:
        return None


def ago(days: int) -> str:
    """How long ago, as a person says it: "today", "3 days ago", "two weeks
    ago", "5 months ago", "a year ago"."""
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{realise.count_word(days)} days ago"
    if days < 60:
        return f"{realise.count_word(realise.weeks_gone(days))} weeks ago"
    if days < 548:
        return f"{realise.count_word(round(days / 30.4))} months ago"
    years = round(days / 365.25)
    return f"{realise.count_word(years)} years ago"


def where_asked(question: str) -> list[str]:
    """The subject words of "where did I write about squats", or []."""
    found = _WHERE.match(question or "")
    if not found:
        return []
    return [t for t in subject_terms(_FILLER.sub("", found.group("rest"))) if t.lower() not in _PREMISE_FILLER]


def _section(content: str, at: int) -> str:
    """The heading the sentence sits under, when it is not the note's own title."""
    heads = list(_HEADING.finditer(content[:at]))
    return heads[-1].group(1).strip() if heads else ""


def _where_tail(out: _Answer, view: NoteView, best, today: date) -> None:  # noqa: ANN001
    """The section, the category and the age, said after the note's name."""
    content = str(view.note.get("content") or "")
    if view.titled and (section := _section(content, best.start)):
        out.parts.append(("template", ", under "))
        out.parts.append(("term", section, view.id))
    category = str(view.note.get("category") or "").strip()
    if category and category.lower() not in ("uncategorised", "uncategorized"):
        out.parts.append(("template", ", in "))
        out.parts.append(("filed", category, view.id))
    edited = _edited_day(view.note)
    changed, verb = (edited, "last edited") if edited else (view.written, "written")
    if changed:
        out.parts.append(("template", f", {verb} "))
        out.m(ago((today - changed).days))


def _best_sentence(view: NoteView, stems: set[str]):  # noqa: ANN202
    """The sentence of `view` holding most of the subject, or None when none holds any."""
    scored = [(sum(1 for st in stems if _holds(st, set(_words(s.text)))), s) for s in view.sentences]
    best = max(scored, key=lambda p: (p[0], -p[1].order), default=(0, None))
    return best[1] if best[0] else None


def where_written(question: str, notes: list[dict], *, today: date | None = None) -> dict | None:
    """"It is in Gym plan, under Leg day, in Fitness, last edited 3 days ago."
    from the note's own fields; None when no note holds every word."""
    words = where_asked(question)
    if not words:
        return None
    stems = {_stem(w) for w in words}
    today = today or user_today()
    views = _views(notes)
    held = [v for v in views if all(_holds(st, v.words) for st in stems)]
    if not held:
        return None
    held.sort(key=lambda v: (not stems <= v.title_words, v.rank))
    view = held[0]
    best = _best_sentence(view, stems)
    if best is None:
        return None
    out = _Answer({v.id: v for v in views}, today)
    out.parts.append(("template", "It is in "))
    out.name(view)
    _where_tail(out, view, best, today)
    others = len(held) - 1
    out.parts.append(("template", f". It is in {realise.count_word(others)} other note{'s' if others != 1 else ''} too." if others else "."))
    out.parts.append(("template", " It reads: "))
    out.q(best, words)
    return _result(out.parts, "where", out.rows)


# --- A24: show me something old -------------------------------------------------------

_OLD = re.compile(
    r"^\s*(?:(?:can|could|would) you\s+)?(?:please\s+)?(?:show|give|get|find|pull up|bring up|dig up|surface|remind)(?: me)?\s+"
    r"(?:(?:something|a note|an? (?:old|forgotten) note|one|anything|a thing)\s+(?:that is\s+|that i wrote\s+|i wrote\s+)?)?"
    r"(?:(?:really|very|quite)\s+)?(?:old|forgotten|from (?:a while|ages|long) (?:ago|back)|i(?:'ve| have) (?:forgotten|not seen)(?: in a while)?)"
    r"(?:\s+(?:note|one|thing))?\s*[?.!]*\s*$|^\s*(?:show|give|get)(?: me)?\s+an? (?:old|forgotten) note\s*[?.!]*\s*$",
    re.I,
)

#: The faded end of the notes the pick is made from: `resurface.ranked` hands
#: the route this many, and a loose list is cut to the oldest of them.
OLD_POOL = 6


def asks_old(question: str) -> bool:
    return bool(_OLD.match(question or ""))


def _pick(views: list[NoteView], salt: str, turn: int | None) -> NoteView:
    pool = sorted(views, key=lambda v: (v.written or date.max, v.rank))[:OLD_POOL]
    digest = hashlib.sha1(f"old:{salt}:{turn or 0}".encode()).digest()
    return pool[digest[0] % len(pool)]


def something_old(question: str, notes: list[dict], *, today: date | None = None, salt: str = "", turn: int | None = None) -> dict | None:
    """One old note, chosen by the session's salt from the faded end of the
    notes (`resurface.ranked` for the route's pool): where it is, how long ago
    it was written and how it starts."""
    if not asks_old(question):
        return None
    views = _views(notes)
    if not views:
        return None
    today = today or user_today()
    view = _pick(views, salt, turn)
    first = next((s for s in view.sentences if s.kind in ("prose", "item", "task")), None)
    out = _Answer({v.id: v for v in views}, today)
    out.parts.append(("template", "Here is one from a while back: "))
    out.name(view)
    if view.written:
        out.parts.append(("template", ", written "))
        out.m(ago((today - view.written).days))
    if first is None:
        out.parts.append(("template", "."))
        return _result(out.parts, "what")
    out.parts.append(("template", ". It begins: "))
    out.q(first, [])
    return _result(out.parts, "what", out.rows)


def answer(question: str, notes: list[dict], *, today: date | None = None, salt: str = "", turn: int | None = None) -> dict | None:
    """The first of the three that the question is."""
    return what_if(question, notes, today=today) or where_written(question, notes, today=today) or something_old(question, notes, today=today, salt=salt, turn=turn)
