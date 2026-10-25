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
from tessellate.ai.composer_study import Ctx, Reply, pick

#: A sentence worth reading for a date at all; the recogniser only runs on these.
_DATEISH = re.compile(
    r"\d{1,2}(?:st|nd|rd|th)\b|\d{1,2}[/.-]\d{1,2}\b|\d{4}-\d\d-\d\d|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b|"
    r"\b(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\b|\b(?:today|tomorrow|tonight|next week|this week|next month|weekend)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9*\"“(\[])")
_DONE = re.compile(r"^\s*[-*+]\s+\[[xX]\]")
#: Only these verbs of a sentence make it a thing to do or attend; "Went to
#: Lisbon on 3 June" in an old note never lands in a future window anyway.
MAX_ITEMS = 14

_LEAD = r"(?:(?:please|pls|can you|could you|hey|ok|okay|so|and|right)[, ]+)*"
_DUE = re.compile(
    rf"^{_LEAD}(?:what(?:'s|’s| is| are| do i have| have i got| have i)?|which|any|anything|show me|show|list|tell me|give me|do i have|have i got|i need to know|check)?\W*"
    r"(?:\w+\W+){0,6}?(?:due|deadlines?|coming up|upcoming|on my plate|happening|scheduled|ahead|on the calendar|on the horizon|to hand in|to submit|to do)\b", re.I)
_BUSY = re.compile(
    rf"^{_LEAD}(?:what(?:'s|’s| is)|what do i have|what have i got|anything|am i busy|how busy am i|how busy is|what does)\s*(?:on|my|the)?\s*(?:\w+\s+){{0,2}}?(?:this|next|today|tomorrow|tonight|the week|my week|the weekend|week|weekend)", re.I)
_PLAN = re.compile(
    rf"^{_LEAD}(?:help me |can you |could you |let'?s |lets )?(?:plan|organi[sz]e|schedule|map out|sort out|prioriti[sz]e|structure|arrange|lay out)\s+(?:out\s+)?(?P<t>.*)$|"
    rf"^{_LEAD}what should i (?:do|work on|focus on|tackle|start with)(?P<s>.*)$|"
    rf"^{_LEAD}(?:what does|how does) (?P<w>my (?:week|day|schedule|weekend|month))(?: look| looks)?(?: like)?.*$|"
    rf"^{_LEAD}(?:my |the )?(?P<a>week ahead|day ahead|agenda|schedule)(?: for (?P<af>.+))?$|"
    rf"^{_LEAD}(?:give me |show me )?(?:an? )?(?:agenda|schedule|plan|timetable) for (?P<g>.+)$", re.I)
_UNTIL = re.compile(
    r"^(?:so |and |hey |ok |okay )*(?:how (?:long|many days|many weeks|much time|far)(?: is it| is there| do i have| have i got| have we got| left)?(?: until| till| to| before| left until| left till)"
    r"|(?:days|weeks) (?:until|till|to|before|left until)|countdown (?:to|until|for)|time (?:until|till|left until|left before)|how soon is|how close is)\s+(?:my |the |our |this )?(?P<t>.+?)\W*$", re.I)

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
        return today, today + timedelta(days=n), f"the next {n} days"
    phrases = when_words.find(low)
    for _s, _e, phrase in phrases:
        span = when_words.span(phrase, today, "future")
        if span:
            start = max(span[0], today)
            if span[1] < today:
                continue
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


def note_events(ctx: Ctx, start: date, end: date) -> list[Event]:
    """The dated sentences of the notes that fall in [start, end]."""
    out: list[Event] = []
    for note in ctx.notes[:400]:
        content = str(note.get("content") or "")
        if not _DATEISH.search(content):
            continue
        anchor = _anchor(note, ctx.now)
        title = study.title_of(content)
        for line in content.splitlines():
            if not line.strip() or _DONE.match(line) or not _DATEISH.search(line) or line.lstrip().startswith(("```", ">")):
                continue
            for sentence in _SENTENCE.split(line):
                if not _DATEISH.search(sentence):
                    continue
                for span in recognise.recognise(sentence, now=anchor, tense="future"):
                    if span.rank or span.kind not in ("date", "datetime"):
                        continue
                    value = span.value
                    day = value.date() if isinstance(value, datetime) else value if isinstance(value, date) else None
                    if day is None or not (start <= day <= end):
                        continue
                    text = _plain(sentence)
                    if re.match(r"^#+\s", sentence.strip()):
                        text = _plain(sentence.lstrip("# "))
                    if 3 <= len(text) <= 160:
                        out.append(Event(day, text, "note", note.get("id"), title))
                    break
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


def _due(ctx: Ctx, win: tuple[date, date, str]) -> Reply:
    start, end, said = win
    today = ctx.now.date()
    found, overdue = events(ctx, start, end)
    span = _range_words(start, end, said, today)
    if not found and not overdue:
        later = _next_after(ctx, end)
        text = pick(ctx.seed, "dueempty", (
            f"Nothing is dated for {span}: no reminder and no note gives a day in it.",
            f"{span.capitalize() if not span[0].isupper() else span} looks clear. No reminder and no dated sentence in your notes falls there.",
        ))
        if later:
            text += f" The next thing is {later.day and _long(later.day)}: {later.text}."
        return Reply(text, asks=["Plan my week"])
    head = pick(ctx.seed, "duehead", (
        f"Coming up, {span}: {len(found)} thing{'s' if len(found) != 1 else ''}.",
        f"Here is what is due or dated for {span}, {len(found)} in all.",
        f"{len(found)} dated item{'s' if len(found) != 1 else ''} for {span}:",
    )) if found else f"Nothing new is dated for {span}, but something is overdue."
    lines = [head, *_grouped(found, today)]
    if overdue:
        lines += ["", "**Overdue**"] + [e.line(overdue=True) for e in overdue[:5]]
    return Reply("\n".join(lines), asks=["Plan my week"] if (end - start).days >= 3 else [])


def _next_after(ctx: Ctx, end: date) -> Event | None:
    found, _o = events(ctx, end + timedelta(days=1), end + timedelta(days=120))
    return found[0] if found else None


def _tasks(ctx: Ctx, limit: int = 8) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for note in ctx.notes[:40]:
        for task in study.open_tasks(str(note.get("content") or "")):
            if _DATEISH.search(task) and any(not s.rank for s in recognise.recognise(task, now=_anchor(note, ctx.now), tense="future") if s.kind in ("date", "datetime")):
                continue
            out.append((task, note))
            if len(out) >= limit:
                return out
    return out


def _plan(ctx: Ctx, win: tuple[date, date, str]) -> Reply:
    start, end, said = win
    today = ctx.now.date()
    found, overdue = events(ctx, start, end)
    tasks = _tasks(ctx)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    load = {d: sum(1 for e in found if e.day == d) for d in days}
    span = _range_words(start, end, said, today)
    lines = [pick(ctx.seed, "planhead", (f"Your plan for {span}, from your reminders and notes.", f"Here is {span}, laid out from what you have saved.", f"{span.capitalize() if not span[0].isupper() else span}, as your notes and reminders have it."))]
    if found:
        lines += _grouped(found, today, limit=10)
    else:
        lines += ["", "Nothing is dated in that time."]
    if overdue:
        lines += ["", "**Overdue**"] + [e.line(overdue=True) for e in overdue[:4]]
    if len(days) > 1 and found:
        busiest = max(days, key=lambda d: (load[d], -days.index(d)))
        free = [d for d in days if load[d] == 0 and d.weekday() < 5]
        lines += ["", f"Busiest day: {_long(busiest)} with {load[busiest]}." + (f" Free weekdays: {', '.join(f'{d:%A}' for d in free)}." if free else "")]
    if tasks:
        lines += ["", f"**Open tasks with no day ({len(tasks)})**"]
        work = [d for d in days if d.weekday() < 5] or days
        placed: list[str] = []
        for task, note in tasks:
            lines.append(f"- {task} ([{study.title_of(str(note.get('content') or ''))}](#/notes/{note['id']}))")
        if len(days) > 1:
            for task, _n in tasks[:4]:
                day = min(work, key=lambda d: (load[d], d))
                load[day] += 1
                placed.append(f"{day:%A}: {task}")
            lines += ["", "A way to spread them over the lighter days: " + "; ".join(placed) + "."]
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
    source = f" From your reminder." if ev.kind == "reminder" else f" From {('[' + ev.title + '](#/notes/' + str(ev.note_id) + ')') if ev.title else 'your note'}."
    lead = pick(ctx.seed, "until", (
        f"{subject.strip().capitalize()} is {_days_away(days)} away, on {_long(ev.day)}." if days > 1 else f"{subject.strip().capitalize()} is {_days_away(days)}, {_long(ev.day)}.",
        f"{_long(ev.day).capitalize()} is when it falls, which is {_days_away(days)} from today." if days > 1 else f"That falls {_days_away(days)}: {_long(ev.day)}.",
    ))
    return Reply(f"{lead}{source}\n\n“{ev.text}”")


def answer(ctx: Ctx) -> Reply | None:
    text = " ".join((ctx.question or "").split())
    if not text or len(text) > 200:
        return None
    today = ctx.now.date()
    until = _UNTIL.match(text)
    if until:
        return _until(ctx, until.group("t"))
    plan = _PLAN.match(text)
    if plan:
        said = " ".join(g for g in plan.groups() if g) or "this week"
        win = window(said, today) or window(text, today)
        if win is None:
            low = said.lower()
            if "day" in low or "today" in low or "first" in low or "focus" in low or "start" in low:
                win = (today, today, "today")
            else:
                win = (today, today + timedelta(days=6 - today.weekday()) if today.weekday() < 6 else today, "this week")
        return _plan(ctx, win)
    if _DUE.match(text) or _BUSY.match(text):
        win = window(text, today)
        leftover = {s for s in _stems(re.sub(r"[^\w\s']", " ", text)) if s not in _FILLER_STEMS}
        if win is not None:
            for _s, _e, phrase in when_words.find(text.lower()):
                leftover -= _stems(phrase)
        if leftover:
            return None
        if win is None:
            win = (today, today + timedelta(days=6), "the next 7 days")
        return _due(ctx, win)
    return None
