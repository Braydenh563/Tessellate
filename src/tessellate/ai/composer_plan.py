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
_BUSY = re.compile(rf"^{_LEAD}(?:what(?:'s|’s| is)|what do i have|what have i got|anything|am i busy|how busy am i|how busy is|what does|what am i (?:doing|up to)|what are we (?:doing|up to))\b", re.I)
#: "what is overdue", "anything overdue", "show me overdue reminders": the
#: overdue reminders alone, never every reminder. Each optional part opens with
#: its own word, so the match is linear.
_OVERDUE = re.compile(
    rf"^{_LEAD}(?:what(?:'s|’s| is| are)?|which|anything|any|show me|show|list|tell me|give me|do i have|have i got|is there anything|is anything)?"
    r"(?: what(?:'s|’s| is| are)?)?(?: (?:the|my|any|all|every))*(?: (?:reminders?|tasks?|items?|things?))?(?: (?:that|which))?(?: (?:is|are))?(?: now)? ?(?:overdue|past due)"
    r"(?: (?:reminders?|tasks?|items?|things?))?(?: for me)?\W*$", re.I)
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
    #: "what's still to do" (INBOX 1357, class I: it listed the newest notes).
    r"|what(?:'s| is)?\s+(?:still|left)\s+to\s+do"
    r"|what\s+(?:do|should)\s+i\s+(?:still\s+)?(?:have|need)\s+to\s+(?:do|finish|get done|tick off)"
    r"|(?:show|list|give)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?(?:open|unfinished|outstanding|remaining|unticked)\s+(?:tasks|items|to-?dos|checklists?|checklist items))\W*$", re.I)
_WHEN_IS = re.compile(rf"^{_LEAD}when(?:'s|’s| is| are| was)\s+(?:my |the |our |this |that )?(?P<t>.+?)\W*$", re.I)
#: The other ways to ask when a thing is: "what date is my exam", "when do I
#: have my exam", "what day is the lab".
_WHEN_IS_ALT = re.compile(
    rf"^{_LEAD}(?:what (?:date|day|time)(?:'s| is| are| was)(?: it)?(?: for)?|when (?:do|did|will|shall) (?:i|we) (?:have|sit|take|do)|when am i (?:sitting|having|taking|doing))"
    r"\s+(?:my |the |our |this |that )?(?P<t>.+?)\W*$", re.I)
#: "What's my next exam", "exam date", "my exam day": the same ask as "when
#: is my exam" (composer5); a reminder must name the subject, else the notes'
#: reader answers.
_WHEN_IS_NEXT = re.compile(
    rf"^{_LEAD}(?:what(?:'s|’s| is| are) (?:my |the |our )?next\s+(?P<t>.+?)"
    r"|(?:my |the |our )?(?P<t2>\S.*?) (?:date|day|deadline|time))\W*$", re.I)
#: "the next 7 days", "next two weeks", "the coming month", "the rest of this
#: week": a span in units. Every part is a fixed word, so the match is linear.
_UNIT_N = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "few": 3, "couple of": 2}
_SPAN_WORDS = re.compile(
    r"\b(?P<the>the )?(?P<lead>next|coming|following|upcoming) (?:(?P<n>\d{1,2}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|few|couple of) )?(?P<unit>day|week|month)s?\b"
    r"|\b(?:the )?rest of (?:the|this) week\b", re.I)
#: "before December", "by 15 November", "until Friday": the word and what follows.
_BOUND = re.compile(r"\b(before|by|until|till)\b", re.I)
_PAST_SAID = re.compile(r"\b(?:was|were|did|had|happened|wrote|made|went|saw|doing|done|been)\b", re.I)
#: "What do I have on the 17th", "what am I doing on the 17th" ask of days to
#: come, the present tense of a plan (2026-10-30 sweep: read as 17 October).
_AHEAD_SAID = re.compile(r"\b(?:will|going to|coming|upcoming|due|next|ahead|deadlines?|remind(?:er|ers|me)?)\b|"
                         r"\b(?:am i|are we) (?:doing|up to)\b|\b(?:do i|do we) have\b|\bhave (?:i|we) got\b", re.I)
_FILLER_STEMS = frozenset(study.stem(w) for w in (
    "what whats is are do have got any anything due deadlines deadline coming up upcoming on my plate the this next week today tomorrow "
    "tonight weekend month happening scheduled ahead for me tell show list give need know check calendar horizon hand submit plan "
    "organise organize schedule agenda busy look like day rest days few couple month by in a an of to am we doing".split()))


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


def _add_months(day: date, n: int) -> date:
    month = day.month - 1 + n
    year, month = day.year + month // 12, month % 12 + 1
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def _unit_span(low: str, today: date) -> tuple[date, date, str] | None:
    found = _SPAN_WORDS.search(low)
    if not found:
        return None
    if found.group("unit") is None:
        return today, today + timedelta(days=6 - today.weekday()), "the rest of this week"
    raw = found.group("n")
    if raw is None and not (found.group("the") or found.group("lead").lower() != "next"):
        return None  # a bare "next week" is the calendar's (when_words)
    n = int(raw) if raw and raw.isdigit() else _UNIT_N.get(raw or "a", 1)
    unit = found.group("unit").lower()
    end = _add_months(today, n) - timedelta(days=1) if unit == "month" else today + timedelta(days=n * (7 if unit == "week" else 1) - 1)
    return today, end, f"the next {n} {unit}{'s' if n != 1 else ''}"


def _bounded(low: str, today: date) -> tuple[date, date, str] | None:
    """"Before December" ends the day before it starts; "by 15 November" and
    "until Friday" end on that day. A bound that names no day ("before the
    exam") is no window."""
    for found in list(_BOUND.finditer(low))[:3]:
        rest = re.sub(r"^(?:the |end of |the end of )+", "", low[found.end():].lstrip()[:40])
        words = re.findall(r"[a-z0-9]+", rest)[:3]
        said = next((" ".join(words[:k]) for k in (3, 2, 1) if words[:k] and when_words.span(" ".join(words[:k]), today, "future")), "")
        span = when_words.span(said, today, "future") if said else None
        if not span:
            continue
        before = found.group(1).lower() == "before"
        last = span[0] - timedelta(days=1) if before else span[1]
        if last >= today:
            return today, last, f"{found.group(1).lower()} {said}"
    return None


def _dated_phrase(phrase: str, low: str, today: date) -> tuple[date, date] | None:
    """The span of a time phrase. An explicit date ("14 August", "the 25th")
    that is already gone is the day just gone when the question looks back
    ("what was I doing on 2 August") and, with no tense said, when that is the
    nearer reading; "will", "due" or "coming" look ahead."""
    ahead = when_words.span(phrase, today, "future")
    if not ahead or not any(c.isdigit() for c in phrase) or ahead[2] != "day":
        return ahead[:2] if ahead else None
    gone = when_words.span(phrase, today, "past")
    if not gone or gone[1] >= today and gone != ahead:
        return ahead[:2]
    if _PAST_SAID.search(low) and not _AHEAD_SAID.search(low):
        return gone[:2]
    if _AHEAD_SAID.search(low):
        return ahead[:2]
    return gone[:2] if (today - gone[1]).days < (ahead[0] - today).days else ahead[:2]


def window(question: str, today: date) -> tuple[date, date, str] | None:
    """(first day, last day, how it was said) for the time a question names: the
    one reader every date shape uses. A window ahead is cut at today (the past
    part of a week is not "coming up"); a day gone, read as a lookback, ends
    before today."""
    low = (question or "").lower()[:300]
    span = _unit_span(low, today) or _bounded(low, today)
    if span:
        return span
    for _s, _e, phrase in when_words.find(low):
        found = _dated_phrase(phrase, low, today)
        if not found:
            continue
        if found[1] < today:
            if any(c.isdigit() for c in phrase):
                return found[0], found[1], phrase
            continue
        start = max(found[0], today)
        # On a Saturday or Sunday "this week" cut at today is a day or
        # two; a student asking on Sunday night means the next seven
        # (dogfood 2026-10-25 round 2, item 4).
        if phrase == "this week" and (found[1] - start).days <= 1:
            return start, start + timedelta(days=6), phrase
        return start, found[1], phrase
    return None


def lookback(question: str, today: date) -> bool:
    """Whether the question asks what a day gone held ("what is on 14
    August"): the activity recap answers it (by the day each note was made)."""
    win = window(question, today)
    return win is not None and win[1] < today


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
        # (tests/test_due_in_ask_1018.py). A window it does not know (a
        # weekday, "the next 7 days") has no such path, so it is said here.
        return None if recognise.ahead_window(said) else _nothing_due(ctx, end, span)
    head = compose.head("due", ctx.mood, count=f"{len(found)} dated item{'s' if len(found) != 1 else ''}", span=span) if found \
        else compose.head("due_overdue", ctx.mood, span=span)
    head = compose.sentence_case(head)
    lines = [head, *_grouped(found, today)]
    if overdue:
        lines += ["", "**Overdue**"] + [e.line(overdue=True) for e in overdue[:5]]
    if (end - start).days >= 3:
        lines += _next_reminder(ctx, end, found)
    return Reply("\n".join(lines), asks=["Plan my week"] if (end - start).days >= 3 else [])


def _overdue(ctx: Ctx) -> Reply:
    """The reminders past their day, oldest first; nothing else."""
    late = sorted(_reminder_events(ctx, ctx.now.date(), ctx.now.date())[1], key=lambda e: (e.day, e.at))
    if not late:
        return Reply("Nothing is overdue.")
    n = len(late)
    lines = [f"{n} reminder{'s are' if n != 1 else ' is'} overdue:", ""]
    lines += [e.line(overdue=True) for e in late[:MAX_ITEMS]]
    if n > MAX_ITEMS:
        lines += ["", f"And {n - MAX_ITEMS} more."]
    return Reply("\n".join(lines))


def _nothing_due(ctx: Ctx, end: date, span: str) -> Reply:
    lines = [compose.sentence_case(compose.frame("due_none", ctx.mood, span=span))]
    later, _o = events(ctx, end + timedelta(days=1), end + timedelta(days=3650))
    if later:
        lines += ["", compose.sentence_case(compose.frame("next_due", ctx.mood, what=later[0].text, when=f"{_long(later[0].day)} {later[0].day.year}"))]
    return Reply("\n".join(lines))


def _next_reminder(ctx: Ctx, end: date, found: list[Event]) -> list[str]:
    """A week question never leaves out a waiting reminder that falls after it."""
    if any(ev.kind == "reminder" for ev in found):
        return []
    later, _o = _reminder_events(ctx, end + timedelta(days=1), end + timedelta(days=3650))
    return ["", f"Next reminder waiting: {later[0].text} ({_long(later[0].day)} {later[0].day.year})."] if later else []



#: Every open checklist item is counted and shown: the plan and "what is left"
#: read the same list (audit 1029 C28).
OPEN_LIMIT = 40


def _tasks(ctx: Ctx, start: date, end: date) -> list[tuple[str, dict, bool]]:
    """(task, its note, whether it names a day outside the window) for every
    open item; one that names a day inside the window is a dated line already."""
    out: list[tuple[str, dict, bool]] = []
    for note in ctx.notes[:OPEN_LIMIT]:
        for task in study.open_tasks(str(note.get("content") or "")):
            day = _sentence_day(task, _anchor(note, ctx.now)) if recognise.dated_sentence(task) else None
            if day is not None and start <= day <= end:
                continue
            out.append((task, note, day is not None))
            if len(out) >= OPEN_LIMIT:
                return out
    return out


def _busiest(found: list[Event], days: list[date], load: dict) -> str:
    busiest = max(days, key=lambda d: (load[d], -days.index(d)))
    free = [d for d in days if load[d] == 0 and d.weekday() < 5]
    return f"Busiest day: {_long(busiest)} with {load[busiest]}." + (f" Free weekdays: {', '.join(f'{d:%A}' for d in free)}." if free else "")


def _task_groups(tasks: list) -> list[str]:
    lines: list[str] = []
    for heading, rows in (("Open tasks with no day", [t for t in tasks if not t[2]]), ("Open tasks dated outside this time", [t for t in tasks if t[2]])):
        if rows:
            lines += ["", f"**{heading} ({len(rows)})**"]
            lines += [f"- {task} ([{study.title_of(str(note.get('content') or ''))}](#/notes/{note['id']}))" for task, note, _d in rows]
    return lines


def _spread_line(undated: list, days: list[date], load: dict) -> list[str]:
    work = [d for d in days if d.weekday() < 5] or days
    placed: dict[date, list[str]] = {}
    for task in undated:
        day = min(work, key=lambda d: (load[d], d))
        load[day] += 1
        placed.setdefault(day, []).append(task)
    return ["", "A way to spread them over the lighter days: " + "; ".join(f"{d:%A}: {', '.join(t)}" for d, t in sorted(placed.items())) + "."]


def _task_lines(tasks: list, days: list[date], load: dict) -> list[str]:
    lines = _task_groups(tasks)
    undated = [t[0] for t in tasks if not t[2]]
    if len(days) > 1 and undated:
        lines += _spread_line(undated, days, load)
    return lines


def _plan(ctx: Ctx, win: tuple[date, date, str]) -> Reply:
    start, end, said = win
    today = ctx.now.date()
    found, overdue = events(ctx, start, end)
    tasks = _tasks(ctx, start, end)
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


def _event_counting_down_to(found: list[Event], wanted: set, today: date) -> Event | None:
    #: The note titled as the subject answers first (note_rank's order) when
    #: it counts down to a later day: "the dentist" is the Dentist note, not a
    #: "Call the dentist" to-do that names tomorrow (audit 1029 C23).
    titled = next((e for e in found if e.day > today and _stems(e.title) == wanted and wanted <= _stems(e.text + " " + e.title)), None)
    return titled or next((e for e in found if wanted <= _stems(e.text)), None) or next((e for e in found if wanted <= _stems(e.text + " " + e.title)), None)


def _until_source(ev: Event) -> str:
    if ev.kind == "reminder":
        return " From your reminder."
    return f" From {('[' + ev.title + '](#/notes/' + str(ev.note_id) + ')') if ev.title else 'your note'}."


def _until(ctx: Ctx, subject: str) -> Reply | None:
    wanted = _stems(subject) - _FILLER_STEMS
    if not wanted:
        return None
    today = ctx.now.date()
    far = today + timedelta(days=900)
    found, _o = events(ctx, today, far)
    ev = _event_counting_down_to(found, wanted, today)
    if ev is None:
        return None
    days = (ev.day - today).days
    lead = pick(ctx.seed, "until", (
        f"{subject.strip().capitalize()} is {_days_away(days)} away, on {_long(ev.day)}." if days > 1 else f"{subject.strip().capitalize()} is {_days_away(days)}, {_long(ev.day)}.",
        f"{_long(ev.day).capitalize()} is when it falls, which is {_days_away(days)} from today." if days > 1 else f"That falls {_days_away(days)}: {_long(ev.day)}.",
    ))
    return Reply(f"{lead}{_until_source(ev)}\n\n“{ev.text}”")


def _plan_window(text: str, said: str, today: date) -> tuple[date, date, str]:
    win = window(said, today) or window(text, today)
    if win is not None and win[1] >= today:
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


def _open_tasks(ctx: Ctx, limit: int = OPEN_LIMIT) -> list[tuple[str, dict]]:
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
    if when:
        return _when_is(ctx, when.group("t"))
    nxt = _WHEN_IS_NEXT.match(text)
    return _when_is(ctx, nxt.group("t") or nxt.group("t2")) if nxt else None


def _written_from(text: str, today: date) -> bool:
    """"Anything from September", "notes from the last week of September": a
    window said with "from" that is already over asks what was written then
    (the recall's), never what is coming up."""
    low = text.lower()
    for start, _end, phrase in when_words.find(low):
        if phrase.startswith("from ") or low[:start].rstrip().endswith(" from"):
            gone = when_words.span(phrase, today, "past")
            return bool(gone and gone[1] < today)
    return False


def _asks_due(text: str, today: date) -> bool:
    """"What is due", or a bare span ("the next 7 days"), or "what's on" with a window."""
    if _DUE.match(text):
        return not lookback(text, today)
    win = window(text, today)
    return bool((_SPAN_WORDS.search(text) or _BUSY.match(text)) and win is not None and win[1] >= today and not _written_from(text, today))


def answer(ctx: Ctx) -> Reply | None:
    text = " ".join((ctx.question or "").split())
    if not text or len(text) > 200:
        return None
    today = ctx.now.date()
    if _LEFT.match(text):
        return _left(ctx)
    if _OVERDUE.match(text):
        return _overdue(ctx)
    until =_UNTIL.match(text)
    if until:
        return _until(ctx, until.group("t"))
    if (reply := _when_reply(ctx, text)) is not None:
        return reply
    plan = _PLAN.match(text)
    if plan:
        return _plan(ctx, _plan_window(text, " ".join(g for g in plan.groups() if g) or "this week", today))
    return _due_reply(ctx, text, today) if _asks_due(text, today) else None
