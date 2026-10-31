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

from tessellate.ai import composer, composer_versus, filed_name, note_recency, realise, recognise, utilities

#: At most this many lines under the opening; the rest are on the right.
SHOWN = 8

#: How many notes the pool reads (`ai/list_pool.py`): a count that reaches it
#: is a floor, and is said so.
POOL_LIMIT = 300

_ORDER = re.compile(
    #: Word by word, so a run of blanks cannot be split every way (CodeQL).
    r"^(?:is|was|does|will)\s+(?:the\s+|my\s+)?(?P<a>[\w'-]+(?:\s[\w'-]+){0,7}?)\s+(?P<rel>before|after|earlier than|later than|sooner than)\s+(?:the\s+|my\s+)?(?P<b>[\w'-]+(?:\s[\w'-]+){0,7})$",
    re.I,
)
_MENTION = re.compile(
    r"^how (?:many times|often) (?:did|do|have|had) i (?:mention(?:ed)?|(?:write|wrote|written|talk|talked|say|said|jot|jotted down) about)\s+(?:the\s+|my\s+)?(?P<what>[\w' -]{1,40})$",
    re.I,
)
#: "list my notes oldest first", "my notes, newest first", "show all my notes
#: in order": every note, told by the day it was written. The order is a word
#: of its own (never a subject), so it is read before any filing is.
_OLDEST_FIRST = (
    r"oldest first|earliest first|first to last|oldest to (?:newest|latest|most recent)|earliest to latest|from (?:the )?oldest(?: to (?:the )?(?:newest|latest))?"
    r"|(?:in )?chronological(?: order|ly)?|in order|in date order|by date|(?:in )?the order (?:i|they were) (?:wrote|written|made|added)(?: them)?"
)
_NEWEST_FIRST = (
    r"newest first|latest first|most recent first|last to first|newest to (?:oldest|earliest)|latest to (?:oldest|earliest)|from (?:the )?newest(?: to (?:the )?oldest)?"
    r"|(?:in )?reverse(?: chronological)?(?: order|ly)?|backwards"
)
_ORDERED = re.compile(
    r"^(?:(?:can|could|would) you )?(?:please\s+)?(?:(?:list|show(?: me)?|give me|display|sort|order|put|see)\s+)?(?:all\s+)?(?:of\s+)?(?:my|the)\s+(?:notes|entries)"
    rf"(?:\s+(?:sorted|ordered|arranged|listed))?[,\s]*(?:(?:by|from)\s+)?(?P<old>{_OLDEST_FIRST})?(?P<new>{_NEWEST_FIRST})?(?:\s+(?:please|pls))?$",
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


#: Spoken shorthand a hurried hand types (stress run 2026-10-30): "whens" is
#: "when's", and a repair at the end ("no the new one", "I mean the moved
#: one") asks for the newer value, as "now" does.
_NO_APOSTROPHE = re.compile(r"\b(when|where|what|who|how)s\b", re.I)
_REPAIR = re.compile(r"[,;]? (?:no|nah|sorry|i mean|wait),? (?:wait,? )?(?:the )?(?:new|newer|latest|updated|moved|current|rescheduled) one$", re.I)


def clean(question: str) -> str:
    """The question without the stray marks a hurried hand leaves (INBOX 808:
    "'what is there about a gaming mouse?\\\\'" searched with the backslash
    kept): slashes and quotes at its ends, doubled spaces, shorthand."""
    text = " ".join((question or "").split())
    text = text.lstrip("\\/'\"` ").rstrip("\\/'\"` ")
    text = _NO_APOSTROPHE.sub(r"\1's", text)
    if (repair := _REPAIR.search(text.rstrip("?.! "))) is not None:
        kept = text[:repair.start()]
        text = kept if re.search(r"\bnow\b", kept, re.I) else kept + " now"
    return text


def _q(question: str) -> str:
    return clean(question).rstrip("?.! ")


class _Helpers:
    """The digest's day, row, fact and span makers. The digest binds them when
    it loads (`bind`), so this module never imports it back (a cycle)."""

    day = row = fact = span = name = None


_h = _Helpers()


def bind(day, row, fact, span, name) -> None:  # noqa: ANN001
    _h.day, _h.row, _h.fact, _h.span, _h.name = day, row, fact, span, name


def list_target(question: str) -> tuple[str, str] | None:
    """`(name, how)` for "list my work notes" or "everything tagged launch":
    how is "tag", "category" or "either"; None when the question names no
    filing."""
    #: One rule with the overview (CHAT_PLAN decision 81): "show me my X notes"
    #: is the notes on X said whole, whether or not a tag has the name; the
    #: listing is "list my X notes" and "notes tagged X".
    if filed_name.shows_the_lot(question):
        return None
    lead = _LIST_LEAD.match(_q(question))
    if not lead:
        bare = filed_name.filed_listing(_q(question))
        return (bare, "either") if bare else None
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
    if not name:
        bare = filed_name.filed_listing(_q(question))
        return (bare, "either") if bare else None
    return (name, how) if name.lower() not in _NOT_A_NAME else None


def window_of(question: str) -> tuple[str, int]:
    """`(how it is said, days ahead)` for a time word in the question: -1 is
    to the month's end, 99999 every date ahead."""
    if re.search(r"\b(?:all|every) (?:the |my )?dates?\b", question, re.I):
        return "ahead in your notes", 99999
    from tessellate.ai import composer_plan

    #: The plan's one default window (audit 1030 Z27).
    return recognise.ahead_window(question) or (f"in {composer_plan.AHEAD_SAID}", composer_plan.AHEAD_DAYS)


def _only_a_window(rest: str | None) -> bool:
    """Whether what follows "what is due" is nothing, or only a time word."""
    if rest is None:  # the "all the dates" and "coming up" shapes name no subject
        return True
    left = re.sub(r"\b(?:in|for|the|my|notes|now|please)\b|[?.!,]", " ", rest.lower())
    return not recognise.without_ahead_words(left).strip()


#: What a "what is due" question asks for besides the time: the kind of date
#: ("exams") narrows the sentences, the rest names whose notes they come from.
_DUE_TRIGGER = re.compile(
    r"\b(?:due|deadlines?|coming up|upcoming|exams?|tests?|quizzes|quiz|assignments?|assessments?|presentations?|"
    r"hand(?:ed)?[ -]in|submit|submission|turn in|scheduled)\b",
    re.I,
)
_DUE_LEAD = re.compile(
    r"^(?:(?:please|pls|hey|ok|okay|so|and|right|can you|could you|just)[, ]+)*"
    r"(?:what(?:'?s)?|which|any|anything|show|list|tell|give|do i have|have i got|i need to know|\w+ (?:deadlines?|exams?|tests?))\b",
    re.I,
)
#: A question about the past or about what a thing is is not a list of dates.
#: Nor is "what do my notes mentioning test say": the word "test" is the thing
#: searched for, not a date asked after (audit 1031 C19).
_DUE_NOT = re.compile(r"\b(?:did|was|were|wrote|written|had|mean|means|about|format|worth|weigh|cover|covers|covered|say|says|mention\w*|contain\w*|hold|holds|holding)\b", re.I)
_KIND_WORDS = frozenset("exam test quiz quizz assignment assessment presentation essay".split())
_DUE_FILLER = frozenset(
    "what what's whats which is are do does i have got any anything the my me our show list tell give need know to for of in on at by a an "
    "this that coming up upcoming due deadline deadlines soon now left please from with and or there it still yet all every scheduled "
    "hand handed submit submission turn out notes note things thing items item tasks task term semester before until till "
    "next days day weeks week months month years year fortnight end rest january february march april may june july august "
    "september october november december monday tuesday wednesday thursday friday saturday sunday".split()
)


_DUE_WORD = re.compile(r"\b(?:due|deadlines?|coming up|upcoming)\b", re.I)


def due_ask(question: str) -> tuple[list[str], list[str], tuple[str, int] | None] | None:
    """`(subject words, kind-of-date words, time window)` of a "what is due"
    question, or None when it is not one (E11). "what is due for uni" has the
    subject "uni"; "what exams do I have" the kind "exam"; neither is a list
    of every date."""
    q = _q(question)
    if not q or len(q.split()) > 14 or not _DUE_TRIGGER.search(q) or not _DUE_LEAD.match(q) or _DUE_NOT.search(q):
        return None
    window = recognise.ahead_window(q)
    rest = recognise.without_ahead_words(q)
    kinds, subject = [], []
    for word in re.findall(r"[\w'&-]+", rest.lower()):
        stem = composer._stem(word)
        if word in _DUE_FILLER or stem in _DUE_FILLER or len(word) < 2 or re.fullmatch(r"\d+(?:st|nd|rd|th)?", word):
            continue
        (kinds if stem in _KIND_WORDS else subject).append(stem)
    return subject, kinds, window


def list_order(question: str) -> str | None:
    """"oldest" or "newest" for a request to list every note in an order, else None."""
    found = _ORDERED.match(_q(question))
    if not found or not (found.group("old") or found.group("new")):
        return None
    return "oldest" if found.group("old") else "newest"


def counted_order(question: str) -> tuple[bool, int, str] | None:
    """`(oldest, how many, subject)` of "my 2 latest baking notes", "the 3 oldest
    notes", "my first two notes about Atlas": a count said, at one end of the
    order, of the notes on a subject (every note when the end is the oldest).
    A "which note is the oldest" is the versus lead's, not this."""
    q = _q(question)
    found = note_recency.recency(q)
    if found is None or not found.said_count or not (found.subject or found.oldest) or composer_versus.asks(q):
        return None
    return found.oldest, found.count, found.subject


def kind(question: str) -> str | None:
    """Which computed shape `question` is, or None."""
    q = _q(question)
    if not q:
        return None
    if utilities.until_subject(q):
        return "until"
    if list_order(q):
        return "ordered"
    if counted_order(q):
        return "counted"
    if _ORDER.match(q):
        return "order"
    if _MENTION.match(q):
        return "mentions"
    if composer_versus.asks(q):
        return "which"
    if holding_ask(q):
        return "holding"
    due = due_ask(q)
    found = _DATES.search(q)
    if found and _only_a_window(found.group("rest")):
        return "dates"
    #: A due question that names a subject or a kind is not the list of every
    #: date: `computed_kind` offers it as "due_for", which only answers when
    #: the notes are filed under that name.
    if due is not None and not (due[0] or due[1]):
        return "dates"
    if list_target(q):
        return "listed"
    return None


def computed_kind(question: str) -> str | None:
    """`kind`, or "due_for" for a "what is due for uni" question: a shape that
    is tried on the notes and falls back to the ordinary answer when none is
    filed under the subject (`_due_for` returns False)."""
    which = kind(question)
    if which not in (None, "dates", "listed"):
        return which
    due = due_ask(_q(question))
    return "due_for" if due is not None and (due[0] or due[1]) else which


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
    #: The note titled as the subject first, then one whose title holds it
    #: (note_rank's order): "the dentist" is the Dentist note, not the
    #: "Call the dentist" to-do that happens to name tomorrow.
    for view in sorted(views, key=lambda v: (v.title_words != wanted, not wanted <= v.title_words, v.rank)):
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
        line = f"{the} is tomorrow." if tense == "future" else f"{the} was yesterday."
    #: The distance first, then the day, as every timed answer says it (INBOX
    #: 1483): "was nine days ago, on 2 October", "is 23 days from today, on 3
    #: November" (the words "how many days until" is answered in); the count asked
    #: for stays exact.
    elif tense == "future":
        line = f"{the} is {realise.count_word(n)} days from today, on {_day(day, today)}."
    else:
        line = f"{the} was {realise.count_word(n)} days ago, on {_day(day, today)}."
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


def _naming(views: list, subject: str, oldest: bool) -> list:
    """The notes that carry every word of `subject`, the end asked for first."""
    wanted = {composer._stem(w) for w in subject.split()}  # noqa: SLF001
    named = [v for v in views if v.sentences and wanted <= {composer._stem(w) for w in (*v.words, *v.title_words, *v.filed_words)}]  # noqa: SLF001
    return sorted(named, key=lambda v: (v.written or date.min, v.rank), reverse=not oldest)


def _counted(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """The notes at one end of the order, as many as were asked for: "Your two
    newest notes about baking:", each by its title and day."""
    oldest, count, subject = counted_order(asked) or (False, 0, "")
    members = _naming(views, subject, oldest)[:min(count, SHOWN)]
    if not members:
        return False
    lines = [(f"{_title(view)}, {_day(view.written, today)}" if view.written else _title(view), view, view.sentences[0]) for view in members]
    end = "oldest" if oldest else "newest"
    many = len(members) > 1
    head = f"Your {realise.count_word(len(members)) + ' ' if many else ''}{end} {'notes' if many else 'note'}"
    _block(out, head + (f" about {subject}:" if subject else ":"), lines)
    if len(members) < count:
        out.lines.append(f"That is all there are{' on that' if subject else ''}.")
    return True


def _ordered(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """The notes in the order asked: the first eight, each by its title and day."""
    oldest = list_order(asked) == "oldest"
    members = sorted((v for v in views if v.sentences), key=lambda v: (v.written or date.min, v.rank), reverse=not oldest)
    if not members:
        return False
    shown = members[:SHOWN]
    lines = [(f"{_title(view)}, {_day(view.written, today)}" if view.written else _title(view), view, view.sentences[0]) for view in shown]
    which = "oldest" if oldest else "newest"
    _block(out, f"Your notes, {which} first:", lines)
    if len(members) > SHOWN:
        out.lines.append(f"{'More' if len(members) >= POOL_LIMIT else realise.count_word(len(members) - SHOWN).capitalize() + ' more'} are on the right.")
    return True


def _which(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """"Which trip is sooner", "which note is the oldest about baking": the
    notes on the subject ranked by the word, the figures or days first."""
    versus = composer_versus.which_one(_q(asked), views, today, composer._stem)
    if versus is None:
        return False
    lines = []
    for row in versus.rows[:4]:
        sentence = next((s for s in row.view.sentences if row.at is not None and s.start <= row.at < s.end), None) or (row.view.sentences[0] if row.view.sentences else None)
        if sentence is not None:
            lines.append((_trim(sentence.text), row.view, sentence))
    _block(out, composer_versus.said(versus, _h.name), lines)
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


#: A first line that is itself an item: a list with no title is named by
#: where it is filed, never "[x] Milk" (stress run 2026-10-30).
_LIST_LINE = re.compile(r"^\s*(?:(?:[-*+]|\d{1,3}[.)])\s+)?\[[ xX]\]|^\s*[-*+]\s")


def _named_by_filing(view) -> str:  # noqa: ANN001
    tags = view.note.get("tags") or []
    tags = tags.split(",") if isinstance(tags, str) else tags
    label = next((str(t).strip() for t in tags if str(t).strip() and str(t).strip().lower() not in {"checklist", "list", "todo"}), "")
    label = label or str(view.note.get("category") or "").strip()
    return f"your {label.lower()} list" if label else "your untitled list"


def _title(view) -> str:  # noqa: ANN001
    if view.titled:
        first = view.title
    else:
        #: The note's first line, not its first unit: "Launch checklist:" is
        #: the name of a list whose first item is "domain".
        line = next((ln for ln in str(view.note.get("content") or "").splitlines() if ln.strip()), view.title)
        if _LIST_LINE.match(line):
            return _named_by_filing(view)
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


_BEFORE = re.compile(r"\b(before|by|until|till)\s+(?:the\s+)?(?:end of\s+)?(?P<when>[a-z0-9 ]{2,24}?)\s*[?.!]*$", re.I)


def _due_window(asked: str, window: tuple[str, int] | None, today: date) -> tuple[date, date, str]:
    """`(first day, last day, how it is said)` of the time a due question
    names: its own words ("this week", "soon"), a span or day the plan reads
    ("the next 20 days", "on friday"), or "before / by / until" a day."""
    from tessellate.ai import composer_plan
    from tessellate.ai import when as when_words

    if window:
        said, days = window
        start = today + timedelta(days=7) if said == "next week" else today
        return start, _until_day(said, days, today), said
    bound = _BEFORE.search(asked)
    span = when_words.span(bound.group("when").strip(), today, "future") if bound else None
    if bound and span:
        last = span[0] - timedelta(days=1) if bound.group(1).lower() == "before" else span[1]
        return today, last, f"{bound.group(1).lower()} {bound.group('when').strip()}"
    planned = composer_plan.window(asked, today)
    if planned and planned[1] >= today:
        return planned[0], planned[1], planned[2]
    return today, today + timedelta(days=3650), "ahead in your notes"


def _filed_words(view) -> set[str]:  # noqa: ANN001
    """The words the person filed a note under or named it by: its category,
    tags and heading, as stems."""
    return {composer._stem(w) for w in (*view.title_words, *view.filed_words)}


def _due_candidates(views: list, wanted: set, kinds: list, today: date) -> tuple[list | None, list]:
    """The notes a due question names and their upcoming dated sentences,
    narrowed to the kind it names; (None, []) when it names no filed note."""
    if wanted:
        named = [v for v in views if wanted <= _filed_words(v)] or [v for v in views if wanted <= {composer._stem(w) for w in v.words}]
        if not named:
            return None, []
    else:
        named = list(views)
    items = _upcoming(named, today)
    if kinds:
        items = [i for i in items if set(kinds) & ({composer._stem(w) for w in i[2].words} | _filed_words(i[1]))]
    return named, items


def _due_for(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """Every dated sentence ahead in the notes a "what is due for uni" names
    (their category, tag or heading), or of the kind it names ("exams"), in day
    order and inside the time it names; False when it names nothing the notes
    are filed under, so the question is answered as before."""
    subject, kinds, window = due_ask(asked) or ([], [], None)
    wanted = set(subject)
    named, items = _due_candidates(views, wanted, kinds, today)
    if named is None:
        return False
    start, end, said = _due_window(asked, window, today)
    inside = [i for i in items if start <= i[0] <= end]
    label = " ".join([*(w for w in asked.lower().split() if composer._stem(w) in wanted)]) or " ".join(kinds)
    if not inside:
        if not named or not (subject or kinds) or not _DUE_WORD.search(asked):
            return False
        out.lines.append(f"Nothing in your {label or 'notes'} notes has a day {said}.")
        return True
    _say_due(out, inside, label, said, today)
    return True


def _say_due(out, inside: list, label: str, said: str, today: date) -> None:  # noqa: ANN001
    """The header and the dated lines (at most `SHOWN`) of what is due."""
    first, last = _day(inside[0][0], today), _day(inside[-1][0], today)
    count = realise.count_word(len(inside)).capitalize()
    header = f"One date is {said}: {first}." if len(inside) == 1 else f"{count} dates are {said} for {label or 'your notes'}, {first} to {last}:"
    lines = []
    for day, view, sentence in inside[:SHOWN]:
        text = _trim(sentence.text)
        titled = view.title and composer._stem(view.title.split()[0]) not in {composer._stem(w) for w in sentence.words}
        lines.append((f"{_day(day, today)}: {text}" + (f" ({view.title})" if titled else ""), view, sentence))
    _block(out, header, lines)
    if len(inside) > SHOWN:
        out.lines.append(f"{realise.count_word(len(inside) - SHOWN).capitalize()} more are on the right.")


# --- kind questions (audit 1029 C34) ---------------------------------------------------------
#
# "Which notes have checklists" asks for a KIND of note, not a word to find: it
# is answered from every note's shape (task lines, bullet lines, days), counted.

_HOLD_KIND = {
    "checklist": "tasks", "checklists": "tasks", "task": "tasks", "tasks": "tasks", "todo": "tasks", "todos": "tasks", "to-do": "tasks",
    "to-dos": "tasks", "checkbox": "tasks", "checkboxes": "tasks",
    "date": "dates", "dates": "dates", "deadline": "dates", "deadlines": "dates",
    "list": "items", "lists": "items", "bullet": "items", "bullets": "items",
}
_HOLD_OPEN = frozenset({"open", "unticked", "unchecked", "incomplete", "unfinished", "outstanding"})
#: Words that join the question to its kind and say nothing about it.
_HOLD_JOIN = frozenset("that which with have has contain contains containing include includes any a an some got i do are is there in them me all of my the your".split())
#: Words that may sit beside the kind ("bullet lists", "due dates", "to do lists").
_HOLD_BESIDE = frozenset({"bulleted", "numbered", "check", "to", "do", "due", "new", "item", "items", "task", "checklist"})
_HOLD_LABEL = {"tasks": "checklists", "dates": "dates", "items": "lists"}


def holding_ask(question: str) -> tuple[str, bool, str] | None:
    """`(kind, open_only, mode)` for "which notes have checklists" (mode
    "which"), "how many notes have dates" ("count") or "open checklist items"
    ("items"); None for anything else. Read word by word, so a long question
    costs nothing and "which notes have dates about Lisbon" (a subject, not a
    kind) is left to the search."""
    t = _q(question).lower().split()
    if not 2 <= len(t) <= 12:
        return None
    shaped = _holding_tail(t)
    if shaped is None:
        return None
    tail, mode = shaped
    open_only = bool(_HOLD_OPEN & set(tail))
    tail = [w for w in tail if w not in _HOLD_OPEN]
    if mode == "items":
        return _holding_items(tail, open_only)
    return _holding_kind(tail, open_only, mode)


def _holding_tail(t: list[str]) -> tuple[list[str], str] | None:
    """The words after "notes" and the mode they are asked in, or None."""
    if t[0] in ("which", "what", "list", "show", "find", "give", "how") and ("notes" in t or "entries" in t):
        tail = [w for w in t[min(t.index(x) for x in ("notes", "entries") if x in t) + 1:] if w not in _HOLD_JOIN]
        return tail, "count" if t[:2] == ["how", "many"] else "which"
    if _HOLD_OPEN & set(t) and "notes" not in t:
        return [w for w in t if w not in _HOLD_JOIN and w not in ("what", "show", "list", "give", "find", "which", "still", "across", "me", "tick")], "items"
    return None


def _holding_items(tail: list[str], open_only: bool) -> tuple[str, bool, str] | None:
    """"open checklist items": only the open items of checklists."""
    if not open_only or not tail or any(w not in ("checklist", "checklists", "item", "items") for w in tail):
        return None
    return "tasks", True, "items"


def _holding_kind(tail: list[str], open_only: bool, mode: str) -> tuple[str, bool, str] | None:
    """The kind of note a "which notes" or "how many notes" ask names."""
    kinds = [_HOLD_KIND[w] for w in tail if w in _HOLD_KIND]
    if not tail or any(w not in _HOLD_KIND and w not in _HOLD_BESIDE for w in tail):
        return None
    if kinds:
        return kinds[-1], open_only, mode
    return ("tasks", True, mode) if open_only and tail[-1] in ("item", "items") else None


def _holding_sentences(view, kind: str, open_only: bool, today: date) -> list:  # noqa: ANN001
    """The sentences that make `view` a note of `kind`."""
    if kind == "dates":
        found = [_sentence_at(view, at) for _day_, at in _dated(view, today, "future") + _dated(view, today, "past")]
        return [s for s in found if s is not None]
    if kind == "tasks":
        return [s for s in view.sentences if s.kind == "task" and not (open_only and s.done)]
    return [s for s in view.sentences if s.kind in ("item", "task")]


_TICK = re.compile(r"^\s*[-*+]\s*\[[ xX]\]\s*")


def _holding_detail(view, got: list, kind: str, today: date) -> str:  # noqa: ANN001
    """What makes the note one of its kind, in a few words."""
    if kind == "tasks":
        tasks = [s for s in view.sentences if s.kind == "task"]
        return f"{sum(1 for s in tasks if s.done)} of {len(tasks)} ticked"
    if kind == "dates":
        days = _dated(view, today, "future") or _dated(view, today, "past")
        return _day(days[0][0], today)
    return _plural(len(got), "item")


def _holding(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    kind, open_only, mode = holding_ask(asked)  # type: ignore[misc]
    hits = [(v, got) for v in views if (got := _holding_sentences(v, kind, open_only, today))]
    hits.sort(key=lambda h: (h[0].written or date.min, -h[0].rank), reverse=True)
    label = "open checklist items" if open_only else _HOLD_LABEL[kind]
    if not hits:
        out.lines.append(f"You have no {label}." if mode == "items" else f"None of your notes have {label}.")
        return True
    if mode == "items":
        items = [(v, s) for v, got in hits for s in got]
        header = f"You have {_plural_words(len(items), 'open checklist item')} across {_plural_words(len(hits), 'note')}:"
        lines = [(f"{_TICK.sub('', s.text).strip()}, in {_title(v)}", v, s) for v, s in items[:SHOWN]]
        _block(out, header, lines)
        if len(items) > SHOWN:
            out.lines.append(f"{realise.count_word(len(items) - SHOWN).capitalize()} more are on the right.")
        return True
    verb = "has" if len(hits) == 1 else "have"
    if mode == "count":
        out.lines.append(f"{_plural_words(len(hits), 'note').capitalize()} {verb} {label}.")
        return True
    lines = [(f"{_title(v)}, {_holding_detail(v, got, kind, today)}", v, got[0]) for v, got in hits[:SHOWN]]
    _block(out, f"{_plural_words(len(hits), 'note').capitalize()} {verb} {label}:", lines)
    if len(hits) > SHOWN:
        out.lines.append(f"{realise.count_word(len(hits) - SHOWN).capitalize()} more are on the right.")
    return True


_SHAPES = {"until": _until, "order": _order, "which": _which, "ordered": _ordered, "counted": _counted, "mentions": _mentions, "listed": _listed, "dates": _dates, "due_for": _due_for, "holding": _holding}


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


_COUNT_LEAD = r"^how many (?:(?P<pre>[\w&' -]{1,30}?)\s+)?(?:notes|entries)"
_COUNT_TAIL = r"(?:\s+(?:do i have|have i (?:got|written|saved|made)|are there|did i (?:write|save|make)))?"
_COUNTED = re.compile(
    _COUNT_LEAD + _COUNT_TAIL + r"(?:\s+(?:are\s+)?(?:about|in|on|under|for|tagged(?: with)?|filed under)\s+(?:the\s+|my\s+)?(?P<post>[\w&' -]{1,40}?))?" + r"(?:\s+(?:category|folder|tag))?$",
    re.I,
)


_THINGS = re.compile(
    r"^how many (?P<name>[a-z][\w&' -]{1,30}?)\s+(?:do i have|have i (?:got|saved|written|kept|filed)|are there|did i (?:save|write|keep|file))"
    r"(?:\s+(?:saved|written down|in my notes|so far))?$",
    re.I,
)


def counted_things(question: str) -> str | None:
    """What "how many recipes have I saved" counts: a name to read as a
    category or a tag, or None. The caller counts it only when the name is
    one; "how many km have I run" names neither and goes on to the composer."""
    found = _THINGS.match(_q(question))
    if not found:
        return None
    name = found.group("name").strip().lower()
    if name in _NOT_A_NAME or name.split()[-1] in ("notes", "note", "entries", "times"):
        return None
    return name


def counted_filing(question: str) -> str | None:
    """What "how many notes do I have about work" counts: a name to read as a
    category or a tag, "" for the whole notebook, None when the question is
    not a count of notes (1324: it was answered with a quote of whichever
    note matched best, "41 testers active")."""
    found = _COUNTED.match(_q(question))
    if not found:
        return None
    pre = (found.group("pre") or "").strip().lower()
    post = (found.group("post") or "").strip()
    if pre in _NOT_A_NAME or pre in ("many", "my"):
        pre = ""
    name = post or pre
    if name.lower() in _NOT_A_NAME:
        return ""
    return name
