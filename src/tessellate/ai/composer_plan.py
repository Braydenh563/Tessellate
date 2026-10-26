"""Deadlines and planning with no model: "what's due this week", "plan my
week", "how long until the exam" (INBOX 1351).

The week is read from three places and nothing is guessed: the person's
reminders (not done, not binned), the dates their notes give in a sentence
("Exam on 12 November.", read against the day the note was written, so
"tomorrow" in an old note is not today's tomorrow), and the open checklist
items in their notes. Every line of an answer is a reminder's text, a note's
own sentence, or a count and a weekday worked out here (the composer's rule).

`answer(ctx)` returns a `Reply` or None; None leaves the question to the
older readers (a "what's due in CC?" with a subject is the note search's).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from tessellate.ai import recognise, study
from tessellate.ai import when as when_words
from tessellate.ai import composer_compose as compose
from tessellate.ai.composer_study import Ctx, Reply, pick

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9*\"“(\[])")
_DONE = re.compile(r"^\s*[-*+]\s+\[[xX]\]")
#: Only these verbs of a sentence make it a thing to do or attend; "Went to
#: Lisbon on 3 June" in an old note never lands in a future window anyway.
MAX_ITEMS = 14

_LEAD = r"(?:(?:please|pls|can you|could you|hey|ok|okay|so|and|right)[, ]+)*"
_DUE = re.compile(
    rf"^{_LEAD}(?:what(?:'s|’s| is| are| do i have| have i got| have i)?|which|any|anything|show me|show|list|tell me|give me|do i have|have i got|i need to know|check)?\W*"
    r"(?:\w+\W+){0,6}?(?:due|deadlines?|coming up|upcoming|on my plate|happening|scheduled|ahead|on the calendar|on the horizon|to hand in|to submit|to do)\b", re.I)
#: "what's on", "am I busy": only a question when a time window is also named (`window`).
_BUSY = re.compile(rf"^{_LEAD}(?:what(?:'s|’s| is)|what do i have|what have i got|anything|am i busy|how busy am i|how busy is|what does)\b", re.I)
_PLAN = re.compile(
    rf"^{_LEAD}(?:help me |can you |could you |let'?s |lets )?(?:plan|organi[sz]e|schedule|map out|sort out|prioriti[sz]e|structure|arrange|lay out)\s+(?:out\s+)?(?P<t>.*)$|"
    rf"^{_LEAD}what should i (?:do|work on|focus on|tackle|start with)(?P<s>.*)$|"
    rf"^{_LEAD}(?:what does|how does) (?P<w>my (?:week|day|schedule|weekend|month))(?: look| looks)?(?: like)?.*$|"
    rf"^{_LEAD}(?:my |the )?(?P<a>week ahead|day ahead|agenda|schedule)(?: for (?P<af>.+))?$|"
    rf"^{_LEAD}(?:give me |show me )?(?:an? )?(?:agenda|schedule|plan|timetable) for (?P<g>.+)$", re.I)
_UNTIL = re.compile(
    r"^(?:so |and |hey |ok |okay )*(?:how (?:long|many days|many weeks|much time|far)(?: is it| is there| do i have| have i got| have we got| left)?(?: until| till| to| before| left until| left till)"
    r"|(?:days|weeks) (?:until|till|to|before|left until)|countdown (?:to|until|for)|time (?:until|till|left until|left before)|how soon is|how close is)\s+(?:my |the |our |this )?(?P<t>.+?)\W*$", re.I)

_LEFT = re.compile(
    rf"^{_LEAD}(?:what(?:'s| is| do i have| have i got| have i| else)?\s+(?:still\s+)?(?:left|outstanding|open|unfinished|incomplete|remaining|pending|undone)(?:\s+to\s+do)?"
    r"|what(?:'s| is)?\s+(?:left\s+)?(?:on\s+)?(?:my\s+)?(?:to-?do|todo)(?:\s+list)?"
    r"|what\s+(?:do|should)\s+i\s+(?:still\s+)?(?:have|need)\s+to\s+(?:do|finish|get done|tick off)"
    r"|(?:show|list|give)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?(?:open|unfinished|outstanding|remaining|unticked)\s+(?:tasks|items|to-?dos|checklists?|checklist items))\W*$", re.I)
_WHEN_IS = re.compile(rf"^{_LEAD}when(?:'s|’s| is| are| was)\s+(?:my |the |our |this |that )?(?P<t>.+?)\W*$", re.I)
#: The other ways to ask when a thing is: "what date is my exam", "when do I
#: have my exam", "what day is the lab".
_WHEN_IS_ALT = re.compile(
    rf"^{_LEAD}(?:what (?:date|day|time)(?:'s| is| are| was)(?: it)?(?: for)?|when (?:do|did|will|shall) (?:i|we) (?:have|sit|take|do)|when am i (?:sitting|having|taking|doing))"
    r"\s+(?:my |the |our |this |that )?(?P<t>.+?)\W*$", re.I)
_SPAN_WORDS = re.compile(r"\b(?:the )?(?:next|coming|following) (\d{1,2}|few|couple of) days?\b|\bnext (\d{1,2}) days\b|\bthe rest of (?:the|this) week\b|\brest of (?:the|this) week\b", re.I)
_FILLER_STEMS = frozenset(study.stem(w) for w in (
    "what whats is are do have got any anything due deadlines deadline coming up upcoming on my plate the this next week today tomorrow "
    "tonight weekend month happening scheduled ahead for me tell show list give need know check calendar horizon hand submit plan "
    "organise organize schedule agenda busy look like day rest days few couple month by in a an of to".split()))


@dataclass
class Event:
    day: date
    text: str
    kind: str  # reminder | note
    note_id: int | None = None
    title: str = ""
    at: str = ""
    priority: str = ""

    def line(self, overdue: bool = False) -> str:
        tail = ""
        if self.kind == "reminder":
            when = f"was due {_short(self.day)}, {self.at}" if overdue else self.at
            tail = f" (reminder{', ' + when if when else ''}{', high priority' if self.priority == 'high' else ''})"
        elif self.note_id is not None and self.title:
            tail = f" ([{self.title}](#/notes/{self.note_id}))"
        return f"- {self.text}{tail}"


def _name(day: date, today: date) -> str:
    if day == today:
        return f"Today, {_long(day)}"
    if day == today + timedelta(days=1):
        return f"Tomorrow, {_long(day)}"
    return _long(day)


def _long(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B}"


def _short(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"


def window(question: str, today: date) -> tuple[date, date, str] | None:
    """(first day, last day, how it was said) for the time a question names; the
    past part of a week is cut at today."""
    low = (question or "").lower()
    found = _SPAN_WORDS.search(low)
    if found:
        if "rest of" in found.group(0):
            end = today + timedelta(days=6 - today.weekday())
            return today, end, "the rest of this week"
        raw = found.group(1) or found.group(2)
        n = 3 if raw == "few" else 2 if raw == "couple of" else int(raw)
        return today, today + timedelta(days=n - 1), f"the next {n} days"
    phrases = when_words.find(low)
    for _s, _e, phrase in phrases:
        span = when_words.span(phrase, today, "future")
        if span:
            start = max(span[0], today)
            if span[1] < today:
                continue
            # On a Saturday or Sunday "this week" cut at today is a day or
            # two; a student asking on Sunday night means the next seven
            # (dogfood 2026-10-25 round 2, item 4).
            if phrase == "this week" and (span[1] - start).days <= 1:
                return start, start + timedelta(days=6), phrase
            return start, span[1], phrase
    return None


# --- events -----------------------------------------------------------------------------

def _reminder_events(ctx: Ctx, start: date, end: date) -> tuple[list[Event], list[Event]]:
    coming: list[Event] = []
    overdue: list[Event] = []
    for r in ctx.reminders:
        due = r.get("due_at")
        if not isinstance(due, datetime) or r.get("done"):
            continue
        at = f"{due:%H:%M}"
        ev = Event(due.date(), str(r.get("text") or "").strip(), "reminder", r.get("entry_id"), "", at, str(r.get("priority") or ""))
        if due.date() < ctx.now.date():
            overdue.append(ev)
        elif start <= due.date() <= end:
            coming.append(ev)
    return coming, overdue


def _anchor(note: dict, now: datetime) -> datetime:
    made = note.get("created_at")
    if isinstance(made, datetime):
        return made.replace(tzinfo=None) if made.tzinfo else made
    return now


def _plain(sentence: str) -> str:
    return study.clean(re.sub(r"^\s*(?:[-*+]|\d{1,2}[.)])\s+(?:\[[ xX]\]\s*)?", "", sentence)).strip()


def _sentence_day(sentence: str, anchor: datetime) -> date | None:
    """The day a sentence names, read against the day its note was written:
    its first date, whichever window is asked about."""
    for span in recognise.recognise(sentence, now=anchor, tense="future"):
        if span.rank or span.kind not in ("date", "datetime"):
            continue
        value = span.value
        return value.date() if isinstance(value, datetime) else value if isinstance(value, date) else None
    return None


def _dated_lines(content: str):  # noqa: ANN202
    for line in content.splitlines():
        if line.strip() and not _DONE.match(line) and recognise.dated_sentence(line) and not line.lstrip().startswith(("```", ">")):
            yield from (s for s in _SENTENCE.split(line) if recognise.dated_sentence(s))


#: Reading a note's dates costs the recogniser; the same note is asked about
#: again by every plan, due and countdown turn. Keyed by the note's id, a hash
#: of its text and the day it was written, so an edit is a new key. Holds the
#: days of every dated sentence, whatever window is asked about later.
_DAYS_CACHE: dict[tuple, tuple[tuple[date, str], ...]] = {}
_CACHE_MAX = 1200


def _note_days(note: dict, now: datetime) -> tuple[tuple[date, str], ...]:
    content = str(note.get("content") or "")
    anchor = _anchor(note, now)
    key = (note.get("id"), hash(content), anchor)
    hit = _DAYS_CACHE.get(key)
    if hit is not None:
        return hit
    found: list[tuple[date, str]] = []
    for sentence in _dated_lines(content):
        day = _sentence_day(sentence, anchor)
        text = _plain(sentence.lstrip("# ") if sentence.strip().startswith("#") else sentence)
        if day is not None and 3 <= len(text) <= 160:
            found.append((day, text))
    if len(_DAYS_CACHE) >= _CACHE_MAX:
        _DAYS_CACHE.clear()
    _DAYS_CACHE[key] = tuple(found)
    return _DAYS_CACHE[key]


def _note_events_of(note: dict, now: datetime, start: date, end: date) -> list[Event]:
    title = study.title_of(str(note.get("content") or ""))
    return [Event(day, text, "note", note.get("id"), title) for day, text in _note_days(note, now) if start <= day <= end]


def note_events(ctx: Ctx, start: date, end: date) -> list[Event]:
    """The dated sentences of the notes that fall in [start, end]."""
    out: list[Event] = []
    for note in ctx.notes[:400]:
        if recognise.dated_sentence(str(note.get("content") or "")):
            out += _note_events_of(note, ctx.now, start, end)
    return out


def _stems(text: str) -> set[str]:
    return set(study.content_stems(text))


def _merge(reminders: list[Event], notes: list[Event]) -> list[Event]:
    """A reminder made from a note's sentence is one line, not two."""
    kept = list(reminders)
    seen = {(e.day, frozenset(_stems(e.text))) for e in reminders}
    for e in notes:
        stems = _stems(e.text)
        if any(d == e.day and stems and len(stems & s) / max(1, min(len(stems), len(s))) >= 0.7 for d, s in seen):
            continue
        key = (e.day, frozenset(stems))
        if key in seen:
            continue
        seen.add(key)
        kept.append(e)
    return sorted(kept, key=lambda e: (e.day, e.kind != "reminder", e.at, e.text.lower()))


def events(ctx: Ctx, start: date, end: date) -> tuple[list[Event], list[Event]]:
    coming, overdue = _reminder_events(ctx, start, end)
    return _merge(coming, note_events(ctx, start, end)), overdue


# --- the answers ------------------------------------------------------------------------

def _days_away(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    weeks, rest = divmod(days, 7)
    base = f"{days} days"
    if days >= 14:
        return f"{base} ({weeks} weeks" + (f" and {rest} day{'s' if rest != 1 else ''}" if rest else "") + ")"
    return base + (" (a week)" if days == 7 else "")


def _grouped(found: list[Event], today: date, limit: int = MAX_ITEMS) -> list[str]:
    lines: list[str] = []
    shown = 0
    last = None
    for ev in found:
        if shown >= limit:
            break
        if ev.day != last:
            lines += ["", f"**{_name(ev.day, today)}**"]
            last = ev.day
        lines.append(ev.line())
        shown += 1
    if len(found) > shown:
        lines += ["", f"And {len(found) - shown} more."]
    return lines


def _range_words(start: date, end: date, said: str, today: date) -> str:
    if start == end:
        return _name(start, today)
    if said and said.lower() in ("this week", "next week", "this weekend", "this month", "next month") or said.startswith(("the next", "the rest")):
        return f"{said} ({_short(start)} to {_short(end)})"
    return f"{_short(start)} to {_short(end)}"


def _due(ctx: Ctx, win: tuple[date, date, str]) -> Reply | None:
    start, end, said = win
    today = ctx.now.date()
    found, overdue = events(ctx, start, end)
    span = _range_words(start, end, said, today)
    if not found and not overdue:
        # The reminders path answers an empty window: it names a waiting
        # reminder outside it, or the next day the notes give
        # (tests/test_due_in_ask_1018.py).
        return None
    head = compose.head("due", ctx.mood, count=f"{len(found)} dated item{'s' if len(found) != 1 else ''}", span=span) if found \
        else compose.head("due_overdue", ctx.mood, span=span)
    head = compose.sentence_case(head)
    lines = [head, *_grouped(found, today)]
    if overdue:
        lines += ["", "**Overdue**"] + [e.line(overdue=True) for e in overdue[:5]]
    if (end - start).days >= 3:
        lines += _next_reminder(ctx, end, found)
    return Reply("\n".join(lines), asks=["Plan my week"] if (end - start).days >= 3 else [])


def _next_reminder(ctx: Ctx, end: date, found: list[Event]) -> list[str]:
    """A week question never leaves out a waiting reminder that falls after it."""
    if any(ev.kind == "reminder" for ev in found):
        return []
    later, _o = _reminder_events(ctx, end + timedelta(days=1), end + timedelta(days=3650))
    return ["", f"Next reminder waiting: {later[0].text} ({_long(later[0].day)} {later[0].day.year})."] if later else []



def _tasks(ctx: Ctx, limit: int = 8) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for note in ctx.notes[:40]:
        for task in study.open_tasks(str(note.get("content") or "")):
            if recognise.dated_sentence(task) and any(not s.rank for s in recognise.recognise(task, now=_anchor(note, ctx.now), tense="future") if s.kind in ("date", "datetime")):
                continue
            out.append((task, note))
            if len(out) >= limit:
                return out
    return out


def _busiest(found: list[Event], days: list[date], load: dict) -> str:
    busiest = max(days, key=lambda d: (load[d], -days.index(d)))
    free = [d for d in days if load[d] == 0 and d.weekday() < 5]
    return f"Busiest day: {_long(busiest)} with {load[busiest]}." + (f" Free weekdays: {', '.join(f'{d:%A}' for d in free)}." if free else "")


def _task_lines(tasks: list, days: list[date], load: dict) -> list[str]:
    lines = ["", f"**Open tasks with no day ({len(tasks)})**"]
    for task, note in tasks:
        lines.append(f"- {task} ([{study.title_of(str(note.get('content') or ''))}](#/notes/{note['id']}))")
    if len(days) > 1:
        work = [d for d in days if d.weekday() < 5] or days
        placed: list[str] = []
        for task, _n in tasks[:4]:
            day = min(work, key=lambda d: (load[d], d))
            load[day] += 1
            placed.append(f"{day:%A}: {task}")
        lines += ["", "A way to spread them over the lighter days: " + "; ".join(placed) + "."]
    return lines


def _plan(ctx: Ctx, win: tuple[date, date, str]) -> Reply:
    start, end, said = win
    today = ctx.now.date()
    found, overdue = events(ctx, start, end)
    tasks = _tasks(ctx)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    load = {d: sum(1 for e in found if e.day == d) for d in days}
    span = _range_words(start, end, said, today)
    lines = [compose.sentence_case(compose.head("plan", ctx.mood, span=span))]
    lines += _grouped(found, today, limit=10) if found else ["", "Nothing is dated in that time."]
    if overdue:
        lines += ["", "**Overdue**"] + [e.line(overdue=True) for e in overdue[:4]]
    if len(days) > 1 and found:
        lines += ["", _busiest(found, days, load)]
    if tasks:
        lines += _task_lines(tasks, days, load)
    elif not found and not overdue:
        lines += ["", "No open tasks either. A clear stretch."]
    return Reply("\n".join(lines), asks=["What's due next week"] if said == "this week" else [])


def _until(ctx: Ctx, subject: str) -> Reply | None:
    wanted = _stems(subject) - _FILLER_STEMS
    if not wanted:
        return None
    today = ctx.now.date()
    far = today + timedelta(days=900)
    found, _o = events(ctx, today, far)
    ev = next((e for e in found if wanted <= _stems(e.text)), None) or next((e for e in found if wanted <= _stems(e.text + " " + e.title)), None)
    if ev is None:
        return None
    days = (ev.day - today).days
    source = " From your reminder." if ev.kind == "reminder" else f" From {('[' + ev.title + '](#/notes/' + str(ev.note_id) + ')') if ev.title else 'your note'}."
    lead = pick(ctx.seed, "until", (
        f"{subject.strip().capitalize()} is {_days_away(days)} away, on {_long(ev.day)}." if days > 1 else f"{subject.strip().capitalize()} is {_days_away(days)}, {_long(ev.day)}.",
        f"{_long(ev.day).capitalize()} is when it falls, which is {_days_away(days)} from today." if days > 1 else f"That falls {_days_away(days)}: {_long(ev.day)}.",
    ))
    return Reply(f"{lead}{source}\n\n“{ev.text}”")


def _plan_window(text: str, said: str, today: date) -> tuple[date, date, str]:
    win = window(said, today) or window(text, today)
    if win is not None:
        return win
    low = said.lower()
    if any(w in low for w in ("day", "today", "first", "focus", "start")):
        return today, today, "today"
    return today, today + timedelta(days=6 - today.weekday()) if today.weekday() < 6 else today, "this week"


def _due_reply(ctx: Ctx, text: str, today: date) -> Reply | None:
    win = window(text, today)
    leftover = {s for s in _stems(re.sub(r"[^\w\s']", " ", _SPAN_WORDS.sub(" ", text))) if s not in _FILLER_STEMS}
    if win is not None:
        for _s, _e, phrase in when_words.find(text.lower()):
            leftover -= _stems(phrase)
    if leftover or (win is None and ctx.open_ids):
        return None  # a subject, or "what is the deadline?" with a note open: the notes' (composer_open)
    return _due(ctx, win or (today, today + timedelta(days=6), "the next 7 days"))


# --- what is left ----------------------------------------------------------------------

PHRASES = {
    "left_head": (
        "Here is what is still open: {r} and {t}.",
        "Still to do, from your reminders and your checklists: {r} and {t}.",
        "{r} and {t} are waiting.",
        "What is left, as your notebook has it: {r} and {t}.",
    ),
    "left_none": (
        "Nothing is open: no reminder waiting and no unticked checklist item in your notes.",
        "You are clear. No reminder is waiting and every checklist item is ticked.",
    ),
    "when_head": (
        "Your reminder for {what} is {when}.",
        "{what} is on your reminders for {when}.",
        "You set a reminder for {what}: {when}.",
    ),
    "when_note": (
        "Your note [{title}](#/notes/{id}) says: “{text}”",
        "[{title}](#/notes/{id}) has it too: “{text}”",
    ),
}


def _open_tasks(ctx: Ctx, limit: int = 12) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for note in ctx.notes[:300]:
        out += [(task, note) for task in study.open_tasks(str(note.get("content") or ""))]
        if len(out) >= limit:
            break
    return out[:limit]


def _open_reminders(ctx: Ctx) -> list[dict]:
    rows = [r for r in ctx.reminders if isinstance(r.get("due_at"), datetime) and not r.get("done")]
    return sorted(rows, key=lambda r: r["due_at"])


def _reminder_line(r: dict, today: date) -> str:
    due = r["due_at"]
    late = ", overdue" if due.date() < today else ""
    return f"- {str(r.get('text') or '').strip()} ({_short(due.date())}, {due:%H:%M}{late})"


def _left(ctx: Ctx) -> Reply | None:
    if ctx.open_ids:
        return None  # with a note open, that note's own list (composer_open)
    today = ctx.now.date()
    reminders, tasks = _open_reminders(ctx), _open_tasks(ctx)
    if not reminders and not tasks:
        return Reply(compose.say("left_none", ctx.mood))
    r = f"{len(reminders)} reminder{'s' if len(reminders) != 1 else ''}"
    t = f"{len(tasks)} unticked checklist item{'s' if len(tasks) != 1 else ''}"
    lines = [compose.head("left", ctx.mood, r=r, t=t)]
    if reminders:
        lines += ["", "**Reminders**"] + [_reminder_line(x, today) for x in reminders[:MAX_ITEMS]]
    if tasks:
        lines += ["", "**Open checklist items**"]
        lines += [f"- {task} ([{study.title_of(str(note.get('content') or ''))}](#/notes/{note['id']}))" for task, note in tasks]
    return Reply("\n".join(lines))


def _when_is(ctx: Ctx, subject: str) -> Reply | None:
    """"When is my exam": a reminder that names it first, then the note's own
    sentence. Left to the notes' reader when no reminder does."""
    wanted = _stems(subject) - _FILLER_STEMS
    if not wanted:
        return None
    mine = [r for r in _open_reminders(ctx) if wanted <= _stems(str(r.get("text") or ""))]
    if not mine:
        return None
    today = ctx.now.date()
    due = mine[0]["due_at"]
    when = f"{_name(due.date(), today)} at {due:%H:%M}"
    lines = [pick(ctx.seed, "whenhead", PHRASES["when_head"]).format(what=str(mine[0].get("text") or "").strip(), when=when)]
    far = today + timedelta(days=900)
    #: The note's own sentence, not the merged list: `_merge` folds a note
    #: line that matches its reminder into one, which would hide the note
    #: ("Exam on 12 November, hall B" beside the reminder "Exam").
    found = note_events(ctx, today - timedelta(days=30), far)
    seen = next((e for e in found if wanted <= _stems(e.text + " " + e.title)), None)
    if seen is not None:
        lines.append(pick(ctx.seed, "whennote", PHRASES["when_note"]).format(title=seen.title, id=seen.note_id, text=seen.text))
    return Reply("\n\n".join(lines))


def _when_reply(ctx: Ctx, text: str) -> Reply | None:
    when = _WHEN_IS.match(text) or _WHEN_IS_ALT.match(text)
    return _when_is(ctx, when.group("t")) if when else None


def answer(ctx: Ctx) -> Reply | None:
    text = " ".join((ctx.question or "").split())
    if not text or len(text) > 200:
        return None
    today = ctx.now.date()
    if _LEFT.match(text):
        return _left(ctx)
    until = _UNTIL.match(text)
    if until:
        return _until(ctx, until.group("t"))
    if (reply := _when_reply(ctx, text)) is not None:
        return reply
    plan = _PLAN.match(text)
    if plan:
        return _plan(ctx, _plan_window(text, " ".join(g for g in plan.groups() if g) or "this week", today))
    if _DUE.match(text) or (_BUSY.match(text) and window(text, today) is not None):
        return _due_reply(ctx, text, today)
    return None
