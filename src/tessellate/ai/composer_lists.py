"""The computed answers over the notes' own days, words and filing (CHAT_PLAN
Phase 6 probes P10 to P13; decisions 41 and 70).

"How many days until the dentist", "is the dentist before the boiler
service", "how many times did I mention Porto", "list my work notes" and "what
is due this week" were answered with a quoted note: the digest took the
question first. Each is one sentence worked out from what the notes say (a
day, a count, a filing), then the lines it rests on, each with its mark. The
sentence is a measured one in decision 25's sense: every figure in it is
computed from a sentence the answer cites. `kind` says which shape a question
is; the route widens what the digest reads for these (`ai/neighbours.py`).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from tessellate.ai import composer, realise, recognise, utilities

#: At most this many lines under the opening; the rest are on the right.
SHOWN = 8

#: How many notes the pool reads (`ai/list_pool.py`): a count that reaches it
#: is a floor, and is said so.
POOL_LIMIT = 300

_ORDER = re.compile(
    r"^(?:is|was|does|will)\s+(?:the\s+|my\s+)?(?P<a>[\w' -]{2,40}?)\s+(?P<rel>before|after|earlier than|later than|sooner than)\s+(?:the\s+|my\s+)?(?P<b>[\w' -]{2,40})$",
    re.I,
)
_MENTION = re.compile(
    r"^how (?:many times|often) (?:did|do|have|had) i (?:mention(?:ed)?|(?:write|wrote|written|talk|talked|say|said|jot|jotted down) about)\s+(?:the\s+|my\s+)?(?P<what>[\w' -]{1,40})$",
    re.I,
)
_LIST_LEAD = re.compile(
    r"^(?:please\s+)?(?:list|show(?: me)?|give me|display|what are|which are)\s+(?:all\s+|every\s+|everything\s+|each\s+)?(?:of\s+)?(?:my\s+|the\s+)?",
    re.I,
)
_BY_WORD = re.compile(
    r"^(?:notes?\s+|entries\s+)?(?P<how>tagged(?: with)?(?: the)?|with the tag|in(?: my)?|under|filed under|from)\s+(?:the\s+)?(?P<name>[\w&' -]{1,40}?)(?:\s+(?:notes?|category|folder|tag))?$",
    re.I,
)
_NAME_NOTES = re.compile(r"^(?P<name>[\w&' -]{1,40}?)\s+(?:notes?|entries)$", re.I)
_NOT_A_NAME = frozenset({"notes", "note", "entries", "all", "the", "my", "everything", "me", "it", "them", "these", "those", "ones"})
_DATES = re.compile(
    #: Only a time window may follow the due word: "what are the deadlines for
    #: the tax return" names a subject, so the digest answers it from that note
    #: (`_only_a_window` reads `rest`).
    r"\bwhat(?:'s| is| are)\s+(?:(?:all|every|any)\s+)?(?:the\s+|my\s+)?(?:due|coming up|upcoming|deadlines?|overdue)"
    r"(?:\s+(?:items?|things?|tasks?))?(?P<rest>.*)$|"
    r"\b(?:all|every|any) (?:the |my )?(?:dates?|deadlines?)\b|\bwhat do i have coming up\b",
    re.I,
)


_NOT_A_FILING = frozenset({"your", "our", "their", "his", "her", "its", "recent", "latest", "newest", "last", "new", "old", "oldest", "some", "any", "other"})


def clean(question: str) -> str:
    """The question without the stray marks a hurried hand leaves (INBOX 808:
    "'what is there about a gaming mouse?\\\\'" searched with the backslash
    kept): slashes and quotes at its ends, doubled spaces."""
    text = " ".join((question or "").split())
    return text.lstrip("\\/'\"` ").rstrip("\\/'\"` ")


def _q(question: str) -> str:
    return clean(question).rstrip("?.! ")


class _Helpers:
    """The digest's day, row, fact and span makers. The digest binds them when
    it loads (`bind`), so this module never imports it back (a cycle)."""

    day = row = fact = span = None


_h = _Helpers()


def bind(day, row, fact, span) -> None:  # noqa: ANN001
    _h.day, _h.row, _h.fact, _h.span = day, row, fact, span


def list_target(question: str) -> tuple[str, str] | None:
    """`(name, how)` for "list my work notes" or "everything tagged launch":
    how is "tag", "category" or "either"; None when the question names no
    filing."""
    lead = _LIST_LEAD.match(_q(question))
    if not lead:
        return None
    rest = _q(question)[lead.end():]
    by = _BY_WORD.match(rest)
    if by:
        said = by.group("how").lower()
        how = "tag" if said.startswith(("tagged", "with")) else "category"
        name = by.group("name").strip()
        # A bare "from X" is a place or a source ("show me from Paris"), not a
        # filing: it counts only when the question says notes.
        if said == "from" and not re.match(r"(?:notes?|entries)\b", rest, re.I) and not re.search(r"\b(?:notes?|category|folder|tag)$", rest, re.I):
            return None
    else:
        named = _NAME_NOTES.match(rest)
        how, name = "either", (named.group("name").strip() if named else "")
        if name.split(" ")[0].lower() in _NOT_A_FILING:  # "your recent notes" asks for recency, not a filing
            return None
    return (name, how) if name and name.lower() not in _NOT_A_NAME else None


def window_of(question: str) -> tuple[str, int]:
    """`(how it is said, days ahead)` for a time word in the question: -1 is
    to the month's end, 99999 every date ahead."""
    if re.search(r"\b(?:all|every) (?:the |my )?dates?\b", question, re.I):
        return "ahead in your notes", 99999
    return recognise.ahead_window(question) or ("in the next two weeks", 14)


def _only_a_window(rest: str | None) -> bool:
    """Whether what follows "what is due" is nothing, or only a time word."""
    if rest is None:  # the "all the dates" and "coming up" shapes name no subject
        return True
    left = re.sub(r"\b(?:in|for|the|my|notes|now|please)\b|[?.!,]", " ", rest.lower())
    return not recognise.without_ahead_words(left).strip()


def kind(question: str) -> str | None:
    """Which computed shape `question` is, or None."""
    q = _q(question)
    if not q:
        return None
    if utilities.until_subject(q):
        return "until"
    if _ORDER.match(q):
        return "order"
    if _MENTION.match(q):
        return "mentions"
    found = _DATES.search(q)
    if found and _only_a_window(found.group("rest")):
        return "dates"
    if list_target(q):
        return "listed"
    return None


def _day(d: date, today: date) -> str:
    return _h.day(d, today)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _cite(out, view, sentence, said: str) -> None:  # noqa: ANN001
    out.rows.append(_h.row(said, _h.fact(view, sentence, "", sentence.text)))


def _sentence_at(view, at: int):  # noqa: ANN001
    return next((s for s in view.sentences if s.start <= at < s.end), None)


def _dated(view, today: date, tense: str) -> list[tuple[date, int]]:  # noqa: ANN001
    return composer._days_named(view, today, tense)


def _find(views: list, subject: str, today: date, tense: str):  # noqa: ANN202
    """`(view, day, sentence)` of the note that names `subject` with a day
    nearest today on the side `tense` asks ("future", "past" or "any")."""
    wanted = {composer._stem(w) for w in composer._words(subject) if len(w) > 2} - {composer._stem(w) for w in composer._NOTE_NOUNS}
    if not wanted:
        return None
    for view in sorted(views, key=lambda v: v.rank):
        if not wanted <= {composer._stem(w) for w in composer._words(str(view.note.get("content") or ""))}:
            continue
        days = _dated(view, today, "future") + _dated(view, today, "past") if tense == "any" else _dated(view, today, tense)
        if not days:
            continue
        day, at = min(days, key=lambda d: abs((d[0] - today).days))
        sentence = _sentence_at(view, at)
        if sentence is not None:
            return view, day, sentence
    return None


def _the(subject: str) -> str:
    subject = re.sub(r"^(?:the|my|our)\s+", "", subject.strip(), flags=re.I)
    return subject if subject[:1].isupper() else f"the {subject}"


def _until(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    tense, subject = utilities.until_subject(asked)
    found = _find(views, subject, today, tense)
    if not found:
        return False
    view, day, sentence = found
    the = _the(subject)
    the = the[:1].upper() + the[1:]
    n = abs((day - today).days)
    if n == 0:
        line = f"{the} is today." if tense == "future" else f"{the} was today."
    elif n == 1:
        line = f"{the} is tomorrow, {_day(day, today)}." if tense == "future" else f"{the} was yesterday, {_day(day, today)}."
    elif tense == "future":
        line = f"{the} is on {_day(day, today)}, {n} days from today."
    else:
        line = f"{the} was on {_day(day, today)}, {n} days ago."
    out.lines.append(line)
    _cite(out, view, sentence, line)
    return True


def _order(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    m = _ORDER.match(_q(asked))
    a, b = _find(views, m.group("a"), today, "any"), _find(views, m.group("b"), today, "any")
    if not (a and b):
        return False
    (va, da, sa), (vb, db, sb) = a, b
    ta, tb = _the(m.group("a")), _the(m.group("b"))
    gap = abs((da - db).days)
    if gap == 0:
        line = f"They are on the same day, {_day(da, today)}: {ta} and {tb}."
    else:
        before = m.group("rel").lower() in ("before", "earlier than", "sooner than")
        holds = (da < db) == before
        first, later = (ta, tb) if da < db else (tb, ta)
        d_first, d_later = (da, db) if da < db else (db, da)
        if holds:
            word = "before" if before else "after"
            line = f"Yes, {ta} is on {_day(da, today)}, {_plural(gap, 'day')} {word} {tb} on {_day(db, today)}."
        else:
            line = f"No, {first} comes first: {_day(d_first, today)}, {_plural(gap, 'day')} before {later} on {_day(d_later, today)}."
    out.lines.append(line)
    for view, sentence in ((va, sa), (vb, sb)):
        _cite(out, view, sentence, line)
    return True


def mention_subject(question: str) -> str:
    """What "how many times did I mention X" counts, or an empty string."""
    found = _MENTION.match(_q(question))
    return found.group("what").strip(" \"'") if found else ""


def _mentions(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    what = mention_subject(asked)
    pattern = re.compile(rf"\b{re.escape(what)}(?:s|'s)?\b", re.I)
    counted = [(v, len(pattern.findall(str(v.note.get("content") or "")))) for v in views]
    hits = sorted(((v, n) for v, n in counted if n), key=lambda p: (p[0].written or date.min, p[0].rank))
    if not hits:
        return False
    total = sum(n for _, n in hits)
    times = {1: "once", 2: "twice"}.get(total) or f"{total} times"
    if len(views) >= POOL_LIMIT:
        times = f"at least {times}"
    notes = "one note" if len(hits) == 1 else f"{len(hits)} notes"
    lines = []
    for view, _ in hits[:4]:
        sentence = next((s for s in view.sentences if pattern.search(s.text)), view.sentences[0])
        said = f"{_day(view.written, today)}: {_trim(sentence.text)}" if view.written else _trim(sentence.text)
        lines.append((said, view, sentence))
    _block(out, f"You mentioned {what} {times}, in {notes}, {_h.span([v for v, _ in hits], today)}.", lines)
    return True


def _block(out, header: str, lines: list) -> None:  # noqa: ANN001
    """The opening and its lines as one paragraph (a list reads down), each
    line cited by its note: `lines` are (said, view, sentence)."""
    out.lines.append(header + "".join(f"\n- {said}" for said, _, _ in lines))
    for said, view, sentence in lines:
        _cite(out, view, sentence, said)


def _trim(text: str, width: int = 110) -> str:
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    return text[:width].rsplit(" ", 1)[0].rstrip(",;:") + "..."


def _title(view) -> str:  # noqa: ANN001
    if view.titled:
        first = view.title
    else:
        #: The note's first line, not its first unit: "Launch checklist:" is
        #: the name of a list whose first item is "domain".
        line = next((ln for ln in str(view.note.get("content") or "").splitlines() if ln.strip()), view.title)
        first = re.split(r"(?<=[.!?])\s", line.strip().lstrip("#").strip(), maxsplit=1)[0]
    return _trim(first.strip().rstrip(":.!"), 70)


def _filed(name: str, how: str, views: list) -> tuple[list, str]:
    """The views filed under `name` and how that reads ("in Work" or
    "tagged launch")."""
    key = name.lower().strip()
    variants = {key, key.rstrip("s"), key + "s"}
    by_category = [v for v in views if str(v.note.get("category") or "").lower() in variants]
    by_tag = [v for v in views if {str(t).lower() for t in v.note.get("tags") or []} & variants]
    if how == "tag" or (how == "either" and not by_category):
        return by_tag, f"tagged {name.lower()}"
    if by_category:
        return by_category, f"in {by_category[0].note.get('category')}"
    return [], ""


def _listed(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    name, how = list_target(asked)
    members, where = _filed(name, how, views)
    if not members:
        return False
    members.sort(key=lambda v: (v.written or date.min, -v.rank), reverse=True)
    span = _h.span(members, today).removeprefix("on ")
    shown = [view for view in members[:SHOWN] if view.sentences]
    lines = [(f"{_title(view)}, {_day(view.written, today)}" if view.written else _title(view), view, view.sentences[0]) for view in shown]
    _block(out, f"You have {_plural_words(len(members), 'note')} {where}, {span}:", lines)
    if len(members) > SHOWN:
        out.lines.append(f"{realise.count_word(len(members) - SHOWN).capitalize()} more are on the right.")
    return True


def _plural_words(n: int, word: str) -> str:
    return f"{realise.count_word(n)} {word}" + ("" if n == 1 else "s")


def _upcoming(views: list, today: date) -> list[tuple[date, object, object]]:
    items, seen = [], set()
    for view in views:
        for day, at in _dated(view, today, "future"):
            sentence = _sentence_at(view, at)
            if sentence is not None and (view.id, sentence.start, day) not in seen:
                seen.add((view.id, sentence.start, day))
                items.append((day, view, sentence))
    return sorted(items, key=lambda i: (i[0], i[1].rank))


def _until_day(said: str, days: int, today: date) -> date:
    if days == -1:
        return date(today.year + (today.month == 12), today.month % 12 + 1, 1) - timedelta(days=1)
    if said == "next week":
        return today + timedelta(days=days)
    return today + timedelta(days=min(days, 3650))


def _dates(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    said, days = window_of(_q(asked))
    ahead = _upcoming(views, today)
    if not ahead:
        out.lines.append("I found no day ahead in your notes.")
        return True
    end =_until_day(said, days, today)
    start = today + timedelta(days=7) if said == "next week" else today
    if said == "tomorrow":
        start = end = today + timedelta(days=1)
    inside = [i for i in ahead if start <= i[0] <= end]
    if not inside:
        day, view, sentence = ahead[0]
        out.lines.append(f"Nothing in your notes falls {said}. The next is {_day(day, today)}: {_trim(sentence.text)}")
        _cite(out, view, sentence, f"{_day(day, today)}: {_trim(sentence.text)}")
        return True
    first, last = _day(inside[0][0], today), _day(inside[-1][0], today)
    count = realise.count_word(len(inside)).capitalize()
    if len(inside) == 1:
        header = f"One date falls {said}: {first}."
    elif said == "ahead in your notes":
        header = f"{count} dates are {said}, {first} to {last}:"
    else:
        header = f"{count} dates fall {said}, {first} to {last}:"
    _block(out, header, [(f"{_day(day, today)}: {_trim(sentence.text)}", view, sentence) for day, view, sentence in inside[:SHOWN]])
    return True


_SHAPES = {"until": _until, "order": _order, "mentions": _mentions, "listed": _listed, "dates": _dates}


def answer(out, which: str, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """Say `which` into `out` from `views`; False, with `out` untouched, when
    the notes do not hold what it needs (no such day, no such filing)."""
    return _SHAPES[which](out, asked, views, today)


def holds_days(notes: list[dict], today: date) -> bool:
    """Whether any of `notes` names a day still ahead: when a "what is due"
    question has nothing waiting in Reminders, this says the notes can answer
    it where "You have no reminders waiting" would not."""
    views = [v for v in (composer.read_note(n, i) for i, n in enumerate(notes or [])) if v]
    return bool(_upcoming(views, today))
