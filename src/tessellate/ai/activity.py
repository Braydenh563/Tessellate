"""What the person did in a window, from every kind of thing (owner-1026b
K20: "it should have looked for any notes, documents or boards or maps I used
or made or deleted, it should show my history, mention if I made or edited
smth, what objects or notes they were").

"What did I do last week", "what did I get up to yesterday", "what did I
delete this week", "show my activity this month": read from the rows, not a
search. Notes, documents, boards, mind maps, reminders set and ticked off,
and what went to the bin, each said as made, edited, binned or done, grouped
by day, newest first, each linked where it can be opened. A window with
nothing in it says so by name and gives the nearest days with something on
either side.

A question that names a subject ("what did I write about sourdough last
week") is left to the notes search; only the doing verbs, the window and the
kind words may be in it. Imported on first use (the composer's import budget).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import notebook_stats
from tessellate.ai import when as when_words

#: The doing verbs, by what they ask for. "work on" and "do" are every kind of
#: change; "write", "save" and "jot" stay with the notes recall, which reads
#: what the notes say.
_VERBS = (
    ("made", r"make|made|create[ds]?|created|add(?:ed)?|start(?:ed)?|set up|build|built"),
    ("edited", r"edit(?:ed)?|change[ds]?|changed|update[ds]?|updated|touch(?:ed)?|tweak(?:ed)?|revise[ds]?|revised"),
    ("binned", r"delete[ds]?|deleted|remove[ds]?|removed|bin(?:ned)?|trash(?:ed)?|thr(?:e|o)w (?:away|out)|thrown (?:away|out)|get rid of|got rid of"),
    ("done", r"finish(?:ed)?|complete[ds]?|completed|tick(?:ed)? off|check(?:ed)? off|get done|got done"),
    ("all", r"do|did|done|doing|get up to|got up to|been up to|up to|work(?:ed)? on|working on|been working on|been doing|activity|history|happen(?:ed)?|use[ds]?|used"),
)
_VERB = re.compile(r"\b(?:" + "|".join(f"(?P<{k}>{v})" for k, v in _VERBS) + r")\b", re.I)
#: The person is asking about their own doings.
_OWN = re.compile(r"\b(?:i|i've|i'd|me|my|we|our)\b", re.I)
#: Said of the past: "what do I have on this week" asks what is coming, not
#: what was done, so a bare present "do" is not a recap.
_PAST = re.compile(r"\b(?:did|was|were|been)\b|\b\w+ed\b|\b(?:made|done|built|threw|thrown|got|activity|history)\b", re.I)
#: Words that are neither a subject nor a doing: the question's frame.
_FRAME = frozenset(
    "what which show list tell give me my i i've i'd we our us all everything anything stuff things thing "
    "did do does done have has had been get got up to on in at over during the a an of for this that these "
    "please pls plz can could you u summary summarise summarize recap overview "
    "so far lately recently whole entire full".split()
)
#: The kind words, mapped to the kinds they keep.
_KINDS = (
    ("note", re.compile(r"^notes?$")),
    ("document", re.compile(r"^(?:documents?|docs?)$")),
    ("board", re.compile(r"^(?:white)?boards?$")),
    ("map", re.compile(r"^(?:mind ?maps?|maps?|mindmaps?)$")),
    ("reminder", re.compile(r"^(?:reminders?|tasks?)$")),
)
_KIND_WORD = {"note": "note", "document": "document", "board": "board", "map": "mind map", "reminder": "reminder"}
_LIMIT = 30


@dataclass
class Asked:
    start: date
    end: date
    phrase: str
    verb: str
    kinds: frozenset[str]


def read(question: str, today: date) -> Asked | None:
    """The window, the doing and the kinds of an own-activity question, or
    None when it is not one (no window, no doing, or a subject named)."""
    text = (question or "").strip()
    if not text or len(text) > 200 or not _OWN.search(text):
        return None
    found = when_words.find(text)
    if not found:
        return None
    phrase = found[0][2]
    span = when_words.span(phrase, today, "past")
    if not span or span[0] > today:
        return None
    bare = text.replace(phrase, " ")
    #: The most specific doing wins: "what did I delete" is binned, not "did".
    verb = next((k for k, v in _VERBS if re.search(rf"\b(?:{v})\b", bare, re.I)), None)
    if verb is None:
        return None
    if not _PAST.search(text):
        return None
    rest = re.sub(re.escape(phrase), " ", text, flags=re.I)
    rest = _VERB.sub(" ", rest)
    kinds: set[str] = set()
    for word in re.findall(r"[a-z']+", rest.lower()):
        if word in _FRAME:
            continue
        kind = next((k for k, pattern in _KINDS if pattern.match(word)), None)
        if kind:
            kinds.add(kind)
            continue
        return None
    if verb == "done" and not kinds:
        kinds = {"reminder"}
    return Asked(span[0], min(span[1], today), phrase, verb, frozenset(kinds))


def _day_words(day: date, today: date) -> str:
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    label = f"{day:%a} {day.day} {day:%b}"
    return label if day.year == today.year else f"{label} {day.year}"


def _title_of(content: str) -> str:
    from tessellate.ai import composer

    return (composer._title(content or "")[0] or "Untitled").strip()[:80]


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time(0)), datetime.combine(end + timedelta(days=1), time(0))


def _local(at: datetime | None, zone) -> datetime | None:  # noqa: ANN001
    """A stored instant (UTC) on the person's clock, without its offset."""
    if at is None:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.astimezone(zone).replace(tzinfo=None)


def _entry_kind(entry) -> str:  # noqa: ANN001
    return {"board": "board", "map": "map"}.get(entry.board_kind or "", "note")


def _link(kind: str, ident: int, title: str) -> str:
    path = {"note": "notes", "document": "docs", "board": "library/board", "map": "library/board"}.get(kind)
    return f"[**{title}**](#/{path}/{ident})" if path else f"**{title}**"


def _events(session: Session, start: date, end: date, zone) -> list[tuple[datetime, str, str, str]]:  # noqa: ANN001
    """(when, doing, kind, said) for every change inside the window, on the
    person's clock. The rows are fetched a day wider each side (stored in
    UTC) and cut to the window after the clock change."""
    from tessellate.core.database import Document, Entry, Reminder

    win_lo, win_hi = _bounds(start, end)
    lo, hi = win_lo - timedelta(days=1), win_hi + timedelta(days=1)

    def inside(at: datetime | None) -> datetime | None:
        at = _local(at, zone)
        return at if at is not None and win_lo <= at < win_hi else None

    out: list[tuple[datetime, str, str, str]] = []
    entries = session.scalars(
        select(Entry).where(
            Entry.is_private == False,  # noqa: E712
            Entry.map_topic == False,  # noqa: E712
            Entry.is_draft == False,  # noqa: E712
            ((Entry.created_at >= lo) & (Entry.created_at < hi))
            | ((Entry.edited_at >= lo) & (Entry.edited_at < hi))
            | ((Entry.deleted_at >= lo) & (Entry.deleted_at < hi)),
        )
    ).all()
    for entry in entries:
        kind, title = _entry_kind(entry), _title_of(entry.content)
        said = f"**{title}** (now in the bin)" if entry.is_deleted else _link(kind, entry.id, title)
        made, edited, binned = inside(entry.created_at), inside(entry.edited_at), inside(entry.deleted_at)
        if made:
            out.append((made, "made", kind, said))
        if edited and (not made or edited.date() != made.date()):
            out.append((edited, "edited", kind, said))
        if entry.is_deleted and binned:
            out.append((binned, "binned", kind, f"**{title}**"))
    documents = session.scalars(
        select(Document).where(
            ((Document.created_at >= lo) & (Document.created_at < hi))
            | ((Document.updated_at >= lo) & (Document.updated_at < hi))
            | ((Document.deleted_at >= lo) & (Document.deleted_at < hi))
        )
    ).all()
    for doc in documents:
        title = (doc.title or "Untitled").strip()[:80]
        gone = doc.deleted_at is not None
        said = f"**{title}** (now in the bin)" if gone else _link("document", doc.id, title)
        made, edited, binned = inside(doc.created_at), inside(doc.updated_at), inside(doc.deleted_at)
        if made:
            out.append((made, "made", "document", said))
        if edited and (not made or edited.date() != made.date()):
            out.append((edited, "edited", "document", said))
        if binned:
            out.append((binned, "binned", "document", f"**{title}**"))
    reminders = session.scalars(
        select(Reminder).where(
            ((Reminder.done_at >= lo) & (Reminder.done_at < hi)) | ((Reminder.created_at >= lo) & (Reminder.created_at < hi))
        )
    ).all()
    for reminder in reminders:
        text = (reminder.text or "").strip()[:80]
        done, made = inside(reminder.done_at), inside(reminder.created_at)
        if reminder.done and done:
            out.append((done, "done", "reminder", text))
        if made and reminder.deleted_at is None:
            out.append((made, "made", "reminder", text))
    out.sort(key=lambda row: row[0], reverse=True)
    return out


def _nearest(session: Session, start: date, end: date, zone) -> tuple[date | None, date | None]:  # noqa: ANN001
    """The latest day with something made before the window, the earliest
    after (on the stored clock; a day either way at the edge is fine here)."""
    from tessellate.core.database import Document, Entry

    lo, hi = _bounds(start, end)
    visible = (Entry.is_private == False, Entry.map_topic == False, Entry.is_draft == False)  # noqa: E712
    before = [
        session.scalar(select(func.max(Entry.created_at)).where(Entry.created_at < lo, *visible)),
        session.scalar(select(func.max(Document.created_at)).where(Document.created_at < lo)),
    ]
    after = [
        session.scalar(select(func.min(Entry.created_at)).where(Entry.created_at >= hi, *visible)),
        session.scalar(select(func.min(Document.created_at)).where(Document.created_at >= hi)),
    ]
    b = max((_local(d, zone) for d in before if d), default=None)
    a = min((_local(d, zone) for d in after if d), default=None)
    return (b.date() if b else None), (a.date() if a else None)


def _span(start: date, end: date, today: date) -> str:
    """"12 to 18 October", "28 September to 4 October"."""
    if start.month == end.month and start.year == end.year:
        return f"{start.day} to {_say_day(end, today)}"
    return f"{_say_day(start, today)} to {_say_day(end, today)}"


def _say_day(day: date, today: date) -> str:
    return f"{day.day} {day:%B}" if day.year == today.year else f"{day.day} {day:%B %Y}"


_DOING_WORDS = {"made": "made", "edited": "edited", "binned": "binned", "done": "ticked off"}
_ARTICLE = {"note": "the note", "document": "the document", "board": "the board", "map": "the mind map", "reminder": "the reminder"}
_COUNT = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


def _n(count: int) -> str:
    return _COUNT[count] if count < len(_COUNT) else str(count)


def _clause(doing: str, kind: str, said: str) -> str:
    if kind == "reminder" and doing == "made":
        return f"set {_ARTICLE[kind]} {said}"
    return f"{_DOING_WORDS[doing]} {_ARTICLE[kind]} {said}"


def _window_said(asked: Asked) -> str:
    from tessellate.ai import composer

    return composer.window_said(asked.phrase)


def _empty(asked: Asked, session: Session, today: date, zone) -> str:  # noqa: ANN001
    when = _window_said(asked)
    what = {"made": "made", "edited": "edited", "binned": "binned", "done": "ticked off"}.get(asked.verb, "made, edited or binned")
    things = " or ".join(sorted(_KIND_WORD[k] + "s" for k in asked.kinds)) if asked.kinds else "nothing"
    lead = f"No {things} were {what} {when}." if asked.kinds else f"Nothing was {what} {when}."
    before, after = _nearest(session, asked.start, asked.end, zone)
    if before and after:
        return f"{lead} The nearest days with something new are {_say_day(before, today)} before it and {_say_day(after, today)} after it."
    if before:
        return f"{lead} The last thing before it was made on {_say_day(before, today)}."
    if after:
        return f"{lead} The first thing after it was made on {_say_day(after, today)}."
    return lead


def _summary(rows: list[tuple[datetime, str, str, str]]) -> str:
    counts: dict[str, int] = {}
    kinds: dict[str, set[str]] = {}
    for _, doing, kind, _ in rows:
        counts[doing] = counts.get(doing, 0) + 1
        kinds.setdefault(doing, set()).add(kind)
    parts = []
    for doing, word in (("made", "made"), ("edited", "edited"), ("binned", "binned"), ("done", "ticked off")):
        if counts.get(doing):
            n = counts[doing]
            #: "made seven notes" when they are all one kind, else "things".
            one = next(iter(kinds[doing])) if len(kinds[doing]) == 1 else ""
            noun = (_KIND_WORD[one] if one else "thing") + ("" if n == 1 else "s")
            parts.append(f"{word} {_n(n)} {noun}")
    if len(parts) > 1:
        return ", ".join(parts[:-1]) + " and " + parts[-1]
    return parts[0] if parts else ""


def answer(question: str, session: Session, now: datetime) -> notebook_stats.StatAnswer | None:
    """The activity recap, or None when `question` is not an own-activity
    question with a window."""
    from tessellate.ai import question_noise

    asked_text = question_noise.repair(question_noise.tidy(question or ""))
    today, zone = now.date(), now.tzinfo or timezone.utc
    asked = read(asked_text, today)
    if asked is None:
        return None
    rows = _events(session, asked.start, asked.end, zone)
    if asked.verb in _DOING_WORDS:
        rows = [r for r in rows if r[1] == asked.verb]
    if asked.kinds:
        rows = [r for r in rows if r[2] in asked.kinds]
    if not rows:
        return notebook_stats.StatAnswer(kind="activity", text=_empty(asked, session, today, zone), facts=[])
    when = _window_said(asked)
    head = f"{when[:1].upper()}{when[1:]}" + (f" ({_span(asked.start, asked.end, today)})" if asked.start != asked.end else "")
    lines = [f"{head} you {_summary(rows)}:"]
    by_day: dict[date, list[str]] = {}
    for when_at, doing, kind, said in rows[:_LIMIT]:
        by_day.setdefault(when_at.date(), []).append(_clause(doing, kind, said))
    if asked.start == asked.end:
        #: One day: the head already says which, so no day label per line.
        lines += [f"- {clause[:1].upper()}{clause[1:]}." for clause in by_day.get(asked.start, [])]
    else:
        for day, clauses in by_day.items():
            lines.append(f"- **{_day_words(day, today)}:** " + "; ".join(clauses) + ".")
    if len(rows) > _LIMIT:
        lines.append(f"And {len(rows) - _LIMIT} more.")
    facts = [{"when": r[0].isoformat(), "doing": r[1], "kind": r[2], "what": r[3]} for r in rows[:_LIMIT]]
    return notebook_stats.StatAnswer(kind="activity", text="\n".join(lines), facts=facts)


#: Reminders named per line of the composed week, so it stays a glance.
_WEEK_NAMED = 3


def _named(rows: list, today: date, zone) -> str:  # noqa: ANN001
    said = [f"{(r.text or '').strip()[:80]} ({_say_day(_local(r.due_at, zone).date(), today)})" for r in rows[:_WEEK_NAMED]]
    more = len(rows) - len(said)
    return "; ".join(said) + (f"; and {_n(more)} more" if more > 0 else "") + "."


def week(session: Session, now: datetime) -> str:
    """The weekly digest with no model (owner-1026b K3, the owner: "is it
    possible to have the composer fill more roles the ai usually would?? like
    the weekly digest"): the last seven days said from the rows, what is
    overdue and coming, where the notes went, and the days themselves. Every
    line is a count or a title, so it can be checked by opening it."""
    from tessellate.core.database import Category, Entry, Reminder

    today, zone = now.date(), now.tzinfo or timezone.utc
    start = today - timedelta(days=6)
    lines = ["From your notes, no AI."]
    rows = _events(session, start, today, zone)
    span = _span(start, today, today)
    if rows:
        lines.append(f"In the last 7 days ({span}) you {_summary(rows)}.")
    else:
        lines.append(f"Nothing was made, edited or binned in the last 7 days ({span}).")
    open_ = session.scalars(
        select(Reminder).where(Reminder.done == False, Reminder.deleted_at.is_(None)).order_by(Reminder.due_at)  # noqa: E712
    ).all()
    start_of_today = datetime.combine(today, time(0))
    late = [r for r in open_ if _local(r.due_at, zone) < start_of_today]
    coming = [r for r in open_ if start_of_today <= _local(r.due_at, zone) < start_of_today + timedelta(days=7)]
    if late:
        lines.append("Overdue: " + _named(late, today, zone))
    if coming:
        lines.append("Coming up this week: " + _named(coming, today, zone))
    lo, hi = _bounds(start, today)
    #: Fetched a day wider each side (stored in UTC), then cut on the
    #: person's clock, as `_events` does.
    written = session.execute(
        select(Category.name, Entry.created_at)
        .select_from(Entry)
        .join(Category, Category.id == Entry.category_id)
        .where(Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False,  # noqa: E712
               Entry.map_topic == False, Entry.is_draft == False,  # noqa: E712
               Entry.created_at >= lo - timedelta(days=1), Entry.created_at < hi + timedelta(days=1))
    ).all()
    counts: dict[str, int] = {}
    for name, at in written:
        if lo <= _local(at, zone) < hi:
            counts[name] = counts.get(name, 0) + 1
    made = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    total = sum(n for _, n in made)
    if made and total >= 3 and made[0][1] * 2 > total:
        #: Only a real lean is worth a line: more than half in one place.
        lines.append(f"Most of the week's notes went to {made[0][0]} ({made[0][1]} of {total}).")
    if rows:
        by_day: dict[date, list[str]] = {}
        for when_at, doing, kind, said in rows[:_LIMIT]:
            by_day.setdefault(when_at.date(), []).append(_clause(doing, kind, said))
        lines.append("")
        lines += [f"- **{_day_words(day, today)}:** " + "; ".join(clauses) + "." for day, clauses in by_day.items()]
        if len(rows) > _LIMIT:
            lines.append(f"And {len(rows) - _LIMIT} more.")
    return "\n".join(lines[:1] + [""] + lines[1:])


_BOARD_NOUNS = {"board": "(?:white)?boards?|canvas(?:es)?", "map": "mind ?maps?|mindmaps?|maps?"}
_BOARD_SHOWN = 12


def boards(question: str, session: Session, now: datetime) -> notebook_stats.StatAnswer | None:
    """"show me my boards", "what maps do I have": the boards or mind maps
    themselves, linked, last changed first (INBOX 1357, class F: both were
    answered from the notes' text). None for any other question."""
    from tessellate.ai import act_registry, question_noise
    from tessellate.core.database import Entry

    text = question_noise.repair(question_noise.tidy(question or "")).lower()
    kind = next((k for k, nouns in _BOARD_NOUNS.items() if re.match(act_registry._listing(nouns), text)), None)
    if kind is None:
        return None
    today, zone = now.date(), now.tzinfo or timezone.utc
    rows = [
        e for e in session.scalars(
            select(Entry).where(Entry.is_board == True, Entry.is_deleted == False, Entry.is_private == False)  # noqa: E712
            .order_by(Entry.updated_at.desc())
        ).all()
        if _entry_kind(e) == kind
    ]
    word = _KIND_WORD[kind]
    if not rows:
        return notebook_stats.StatAnswer(kind="boards", text=f"You have no {word}s yet.", facts=[])
    lead = f"You have one {word}:" if len(rows) == 1 else f"You have {_n(len(rows))} {word}s, last changed first:"
    lines = [lead]
    for e in rows[:_BOARD_SHOWN]:
        changed = _local(e.updated_at or e.created_at, zone)
        lines.append(f"- {_link(kind, e.id, _title_of(e.content))} (changed {_say_day(changed.date(), today)})")
    if len(rows) > _BOARD_SHOWN:
        lines.append(f"And {_n(len(rows) - _BOARD_SHOWN)} more in the Library.")
    facts = [{"kind": kind, "id": e.id, "title": _title_of(e.content)} for e in rows[:_BOARD_SHOWN]]
    return notebook_stats.StatAnswer(kind="boards", text="\n".join(lines), facts=facts)
