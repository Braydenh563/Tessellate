"""Who has what, over a list whose lines name a person (L103).

A potluck note ("- Sam: salad") or a chore checklist ("- [ ] Tom: laundry") is a table
of person and thing. "Who is bringing the salad" is Sam, "what is Priya bringing" is her
line, "who is bringing what" is the table, "who still has chores to do" is the open
lines' people. Without this the question was a quote of the first line that held a word.
Only lines shaped `Name: thing` count, and only a list of two or more of them; a note
that is not such a list leaves the question to the other readers (None).
"""

from __future__ import annotations

import re
from datetime import date

from tessellate.ai import composer, composer_lists, realise

#: "- [ ] Tom: laundry", "Sam - salad": a capitalised name of one or two words, a mark, the thing.
_PAIR = re.compile(r"^\s*(?:[-*•]\s*)?(?:\[(?P<box>[ xX])\]\s*)?(?P<who>[A-Z][\w'’]+(?: [A-Z][\w'’]+)?)\s*(?::|\s[-–]\s)\s*(?P<what>\S.{0,80})$")
_AUX = r"(?:is|'s|are|was|will be|has|have|does|did)"
_WHO_WHAT = re.compile(rf"^who {_AUX}? ?(?P<verb>[a-z]+)? ?what(?: (?:to|for|at|in|on) (?P<where>.+))?$", re.I)
_WHO_THING = re.compile(rf"^who(?:'s| {_AUX})? ?(?P<rest>.+)$", re.I)
_WHOSE = re.compile(r"^whose (?:turn|job|task|chore) (?:is|was) (?:it )?(?:for )?(?P<thing>.+)$", re.I)
_WHAT_PERSON = re.compile(rf"^what {_AUX} (?P<name>[A-Za-z][\w'’]*(?: [A-Za-z][\w'’]*)?) (?P<verb>[a-z]+ing|having|taking|bringing)$", re.I)
_WHO_OPEN = re.compile(r"^who (?:still )?(?:has|have|hasn't|has not|haven't|have not|is yet to|needs to|still needs to|is left to|is left)(?: (?:done|finished|ticked|to))?(?: .+)?$", re.I)
_OPEN_WORDS = ("still", "hasn't", "has not", "haven't", "have not", "yet", "left", "needs", "to do")
_NOISE = frozenset({"the", "a", "an", "their", "his", "her", "my", "our", "your", "to", "of", "on", "in", "for", "at", "with"})


def _pairs(view) -> list[tuple[str, str, object, bool]]:  # noqa: ANN001
    """(who, what, sentence, done) of each `Name: thing` line; a list of fewer than two is no table."""
    found = []
    for s in view.sentences:
        if s.kind not in ("item", "task"):
            continue
        m = _PAIR.match(s.text or "")
        if m:
            found.append((m.group("who"), m.group("what").strip().rstrip("."), s, bool(s.done) or (m.group("box") or " ").lower() == "x"))
    return found if len(found) >= 2 else []


def _tables(views: list) -> list[tuple[object, list]]:
    return [(v, p) for v in views if (p := _pairs(v))]


def _words(text: str) -> set[str]:
    return {w for w in composer._words(text) if w not in _NOISE}  # noqa: SLF001


def _holding(tables: list, thing: str) -> list[tuple[object, tuple]]:
    wanted = [w for w in composer._words(thing) if w not in _NOISE]  # noqa: SLF001
    if not wanted:
        return []
    return [(v, p) for v, pairs in tables for p in pairs if all(composer._holds(composer._stem(w), _words(p[1])) for w in wanted)]  # noqa: SLF001


def _said(out, view, lines: list[str], hits: list) -> None:  # noqa: ANN001
    for (_v, pair), said in zip(hits, lines, strict=False):
        composer_lists._cite(out, view, pair[2], said)  # noqa: SLF001


def _table(out, tables: list, where: str) -> bool:  # noqa: ANN001
    wanted = [w for w in composer._words(where or "") if w not in _NOISE]  # noqa: SLF001
    view, pairs = next(((v, p) for v, p in tables if not wanted or all(composer._holds(composer._stem(w), v.title_words | v.words) for w in wanted)), (None, None))  # noqa: SLF001
    if view is None:
        return False
    title = composer_lists._title(view)  # noqa: SLF001
    composer_lists._block(out, f"{title} says who has what:", [(f"{who}: {what}", view, s) for who, what, s, _d in pairs])  # noqa: SLF001
    return True


def _thing(out, tables: list, who: str, aux: str, rest: str) -> bool:  # noqa: ANN001
    verb_free = " ".join(w for w in rest.split() if w.lower() not in {"is", "are", "doing", "bringing", "making", "taking", "having", "getting", "buying", "cooking", "cleaning", "responsible", "for", "in", "charge", "of", "going", "to", "be", "bring", "do", "make", "take", "get", "buy"})
    hits = _holding(tables, verb_free)
    if not hits:
        return False
    names = realise.join_items(list(dict.fromkeys(p[0] for _v, p in hits)))
    plural = len(set(p[0] for _v, p in hits)) > 1
    said = f"{names} {'are' if plural else aux} {rest.rstrip('?.! ')}."
    out.lines.append(said)
    for v, p in hits:
        composer_lists._cite(out, v, p[2], said)  # noqa: SLF001
    return True


def _person(out, tables: list, name: str, verb: str) -> bool:  # noqa: ANN001
    wanted = name.strip().casefold()
    owned = [(v, [p for p in pairs if p[0].casefold() == wanted]) for v, pairs in tables]
    owned = [(v, ps) for v, ps in owned if ps]
    if not owned:
        return False
    who = owned[0][1][0][0]
    if len(owned) == 1:
        said = f"{who} is {verb.lower()} {realise.join_items([p[1] for p in owned[0][1]])}."
    else:
        #: Named on two lists: which is which is the note's, not guessed from the verb.
        said = f"{who} has " + realise.join_items([f"{realise.join_items([p[1] for p in ps])} on {composer_lists._title(v)}" for v, ps in owned]) + "."  # noqa: SLF001
    out.lines.append(said)
    for v, ps in owned:
        for p in ps:
            composer_lists._cite(out, v, p[2], said)  # noqa: SLF001
    return True


def _open_people(out, tables: list, text: str) -> bool:  # noqa: ANN001
    low = text.lower()
    done_wanted = bool(re.search(r"\b(?:has|have) (?:already )?(?:done|finished|ticked|completed)\b", low)) and not any(w in low for w in _OPEN_WORDS)
    boxed = [(v, p) for v, pairs in tables for p in pairs if p[2].kind == "task"]
    hits = [(v, p) for v, p in boxed if p[3] == done_wanted]
    if not boxed or not hits:
        return False
    view = hits[0][0]
    lines = realise.join_items([f"{p[0]} ({p[1]})" for _v, p in hits])
    tail = "have finished" if done_wanted else ("still have" if len(hits) > 1 else "still has") + " something to do"
    said = f"On {composer_lists._title(view)}, {lines} {tail}."  # noqa: SLF001
    out.lines.append(said)
    for v, p in hits:
        composer_lists._cite(out, v, p[2], said)  # noqa: SLF001
    return True


def _whose(out, tables: list, thing: str) -> bool:  # noqa: ANN001
    """"Whose turn is the bins": the people holding that thing."""
    hits = _holding(tables, thing)
    if not hits:
        return False
    names = realise.join_items(list(dict.fromkeys(p[0] for _v, p in hits)))
    said = f"It is {names}{'’s' if len(hits) == 1 else ''} turn for {thing}."
    out.lines.append(said)
    for v, p in hits:
        composer_lists._cite(out, v, p[2], said)  # noqa: SLF001
    return True


def _aux(q: str) -> str:
    """The helping verb a "who ..." question opens with ("is" when it has none)."""
    aux = re.match(rf"^who(?:'s| ({_AUX}))?", q, re.I)
    return (aux.group(1) or "is") if aux else "is"


def answer(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001, ARG001
    """The person-and-thing answer, False when `asked` is not one or no list holds the pair."""
    q = " ".join(composer_lists._q(asked).split()).rstrip("?.! ")  # noqa: SLF001
    low = q.lower()
    if not low.startswith(("who", "what", "whose")):
        return False
    tables = _tables(views)
    if not tables:
        return False
    if (m := _WHAT_PERSON.match(q)) is not None:
        return _person(out, tables, m.group("name"), m.group("verb"))
    if (m := _WHOSE.match(q)) is not None:
        return _whose(out, tables, m.group("thing"))
    if (m := _WHO_WHAT.match(q)) is not None:
        return _table(out, tables, m.group("where") or "")
    if _WHO_OPEN.match(q):
        return _open_people(out, tables, q)
    if (m := _WHO_THING.match(q)) is not None and low.startswith("who"):
        return _thing(out, tables, "", _aux(q), m.group("rest"))
    return False
