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

from tessellate.ai import composer_done, composer_event_verdict, composer_frame, question_noise, realise, recognise, study
from tessellate.ai import recognise_questions
from tessellate.ai import when as when_words
from tessellate.ai import composer_compose as compose
from tessellate.ai import note_rank, reminder_parser
from tessellate.ai.composer_ask import rephrase
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
_BUSY = re.compile(rf"^{_LEAD}(?:what(?:'s|’s| is)|what do i have|what have i got|anything|am i busy|how busy am i|how busy is|what does|what am i (?:doing|up to)|what are we (?:doing|up to)|(?:do|have) (?:i|we) (?:have|got) (?:anything|something)|is there (?:anything|something))\b", re.I)
#: "what is overdue", "anything overdue", "show me overdue reminders": the
#: overdue reminders alone, never every reminder. Each optional part opens with
#: its own word, so the match is linear.
_OVERDUE = re.compile(
    rf"^{_LEAD}(?:what(?:'s|’s| is| are)?|which|anything|any|show me|show|list|tell me|give me|do i have|have i got|is there anything|is anything)?"
    r"(?: what(?:'s|’s| is| are)?)?(?: (?:the|my|any|all|every))*(?: (?:reminders?|tasks?|items?|things?))?(?: (?:that|which))?(?: (?:is|are))?(?: now)? ?(?:overdue|past due)"
    r"(?: (?:reminders?|tasks?|items?|things?))?(?: for me)?\W*$", re.I)
#: "what have I got on", "what's on": the agenda with no day named (R9-8).
_BARE_ON = re.compile(rf"^{_LEAD}what(?:'s|’s| is)? (?:(?:do )?i (?:have|got)|have i got|am i doing) on\W*$|^{_LEAD}what(?:'s|’s) on\W*$", re.I)
#: What the dated list can be narrowed to: "any birthdays coming up" (R9-8).
_KINDS = {"birthday": "birthday", "appointment": "appointment", "meeting": "meeting", "event": "event", "booking": "booking", "trip": "trip", "holiday": "holiday"}
_PLAN = re.compile(
    rf"^{_LEAD}(?:help me |can you |could you |let'?s |lets )?(?:plan|organi[sz]e|schedule|map out|sort out|prioriti[sz]e|structure|arrange|lay out)\s+(?:out\s+)?(?P<t>.*)$|"
    rf"^{_LEAD}what should i (?:do|work on|focus on|tackle|start with)(?P<s>.*)$|"
    #: "what is most important right now", "what's urgent", "what matters most" (L155): the day's plan.
    rf"^{_LEAD}what(?:'s|’s| is| are)? (?:(?:the|my) )?(?P<imp>(?:most |more )?(?:important|urgent|pressing)(?: (?:thing|things|task|tasks|item|items|job|jobs))?(?: to do)?|(?:top |main |biggest )?priorit(?:y|ies)|matters? most)(?: (?:right now|now|today|at the moment|at present|this morning|this afternoon|tonight))?\W*$|"
    rf"^{_LEAD}what(?:'s|’s| is)? my (?P<imp2>most (?:important|urgent|pressing) (?:thing|task|item|job))(?: to do)?(?: (?:right now|now|today))?\W*$|"
    #: "spread these over the week", "how should I spread my tasks this week" (audit 1030 Z57).
    rf"^{_LEAD}(?:how (?:should|do|can|could) i |help me |can you )?spread (?:out )?(?P<sp>.*)$|"
    rf"^{_LEAD}(?:what does|how does) (?P<w>my (?:week|day|schedule|weekend|month))(?: look| looks)?(?: like)?.*$|"
    rf"^{_LEAD}(?:my |the )?(?P<a>week ahead|day ahead|agenda|schedule)(?: for (?P<af>.+))?$|"
    rf"^{_LEAD}(?:give me |show me )?(?:an? )?(?:agenda|schedule|plan|timetable) for (?P<g>.+)$|"
    #: "make a study plan": no model writes it, so the notes' own dated items are laid out (F13 g).
    rf"^{_LEAD}(?:(?:can|could) you )?(?:make|create|build|write|draft|put together|give|get)(?: me)? (?:an? |my )?(?:study|revision|exam) (?:plan|schedule|timetable)(?P<st>.*)$", re.I)
#: "organise everything about the harbor", "sort out my boiler stuff": a topic to file or read, not a week to plan (L-chat-32).
_TOPIC = re.compile(r"\b(?:everything|all (?:my |the )?(?:notes?|things?|stuff)|anything) (?:about|on|to do with|regarding|related to)\b|\b(?:notes?|stuff|things) (?:about|on|to do with|regarding|related to)\b|^(?:my |the )?\w+ (?:stuff|things)$", re.I)


def _topic_target(plan: re.Match | None) -> bool:
    """True when the verb form of `_PLAN` was given a topic and no time to plan it in."""
    target = (plan.group("t") if plan else None) or ""
    return bool(target and _TOPIC.search(target) and not recognise.names_a_time(target))


_UNTIL = re.compile(
    r"^(?:so |and |hey |ok |okay )*(?:how (?:long|many days|many weeks|much time|far)(?: is it| is there| do i have| have i got| have we got| left)?(?: until| till| to| before| left until| left till)"
    r"|(?:days|weeks) (?:until|till|to|before|left until)|countdown (?:to|until|for)|time (?:until|till|left until|left before)|how soon is|how close is)\s+(?:my |the |our |this )?(?P<t>.+?)\W*$", re.I)

_LEFT = re.compile(
    rf"^{_LEAD}(?:what(?:'s| is| do i have| have i got| have i| else)?\s+(?:still\s+)?(?:left|outstanding|open|unfinished|incomplete|remaining|pending|undone)(?:\s+to\s+do)?"
    r"|what(?:'s| is)?\s+(?:left\s+)?(?:on\s+)?(?:my\s+)?(?:to-?do|todo)(?:\s+list)?"
    #: "what's still to do" (INBOX 1357, class I: it listed the newest notes).
    r"|what(?:'s| is)?\s+(?:still|left)\s+to\s+do"
    r"|what\s+(?:do|should)\s+i\s+(?:still\s+)?(?:have|need)\s+to\s+(?:do|finish|get done|tick off)"
    r"|(?:show|list|give)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?(?:open|unfinished|outstanding|remaining|unticked)\s+(?:tasks|items|to-?dos|checklists?|checklist items)"
    #: "what tasks do I have", "what needs doing", "my tasks" (R9-8).
    r"|what\s+(?:tasks?|to-?dos?|chores|jobs)\s+(?:do i have|have i got|are there|are open|are left)(?:\s+(?:open|left|outstanding|to do))?"
    r"|what\s+needs\s+(?:doing|to be done|done)|(?:show|list)\s+(?:me\s+)?my\s+(?:tasks|to-?dos)|my\s+(?:tasks|to-?dos))\W*$", re.I)
_WHEN_IS = re.compile(rf"^{_LEAD}when(?:'s|’s| is| are| was)\s+(?:my |the |our |this |that )?(?P<t>.+?)\W*$", re.I)
#: The other ways to ask when a thing is: "what date is my exam", "when do I
#: have my exam", "what day is the lab".
_WHEN_IS_ALT = re.compile(
    rf"^{_LEAD}(?:what (?:date|day|time)(?:'s| is| are| was)(?: it)?(?: for)?|when (?:do|did|will|shall) (?:i|we) (?:have|sit|take|do)|when am i (?:sitting|having|taking|doing))"
    r"\s+(?:my |the |our |this |that )?(?P<t>.+?)\W*$", re.I)
#: "What's my next exam", "exam date", "my exam day": the same ask as "when
#: is my exam" (composer5); a reminder must name the subject, else the notes'
#: reader answers.
#: "when do the bins go out": the reminder names the thing; a reminder-only ask (audit 2 G3).
_WHEN_DO = re.compile(rf"^{_LEAD}when (?:do|does|will|shall) (?:the |my |our )(?P<t>.+?)\W*$", re.I)
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
    "organise organize schedule agenda busy look like day rest days few couple month by in a an of to am we doing soon important urgent planned".split()))


#: Words that carry no thing in "when do the bins go out" (audit 2 G3).
_LIGHT_STEMS = frozenset(study.stem(w) for w in "go goes going out happen happens happening".split())


@dataclass
class Event:
    day: date
    text: str
    kind: str  # reminder | note
    note_id: int | None = None
    title: str = ""
    at: str = ""
    priority: str = ""
    #: The note's one name for display (`composer_frame.name_of`): the link's words. `title` stays the
    #: note's first line, which the matching below compares.
    shown: str = ""

    def line(self, overdue: bool = False) -> str:
        tail = ""
        if self.kind == "reminder":
            when = f"was due {_short(self.day)}, {self.at}" if overdue else self.at
            tail = f" (reminder{', ' + when if when else ''}{', high priority' if self.priority == 'high' else ''})"
        elif self.note_id is not None and self.title:
            if self._is_title():
                #: The row is the note's own first line, so the link wraps all of it; a second, shortened name beside it would say it twice.
                return f"- [{self.text}](#/notes/{self.note_id})"
            tail = f" ([{self.shown or self.title}](#/notes/{self.note_id}))"
        return f"- {self.text}{tail}"

    def _is_title(self) -> bool:
        """The line is the note's own title (or the words a title-less note is
        named by), so it is the link, said once (audit 1030 Z43)."""
        text, title = self.text.strip().rstrip("."), self.title.strip().rstrip(".")
        cut = title.endswith("…")
        return text.lower() == title.lower() or (cut and text.lower().startswith(title.rstrip("…").strip().lower()))


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
        #: "anything about Christmas" is a topic to search, not a day to list.
        found = None if recognise.a_topic_phrase(low, phrase, holiday=False) else _dated_phrase(phrase, low, today)
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
    seen: set[tuple[str, datetime]] = set()
    for r in ctx.reminders:
        due = r.get("due_at")
        if not isinstance(due, datetime) or r.get("done"):
            continue
        #: The same words at the same minute are one line (audit 1028 E29).
        key = (" ".join(str(r.get("text") or "").split()).casefold(), due.replace(second=0, microsecond=0, tzinfo=None))
        if key in seen:
            continue
        seen.add(key)
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
    spans = [x for x in recognise.recognise(sentence, now=anchor, tense="future") if not x.rank and x.kind in ("date", "datetime")]
    for i, span in enumerate(spans):
        after = spans[i + 1] if i + 1 < len(spans) else None
        if after is not None and _WEEKDAY_ONLY.match(span.text) and 0 <= after.start - span.end <= 2:
            #: "Friday 6 November" is 6 November, never this Friday (Z26).
            span = after
        value = span.value
        return value.date() if isinstance(value, datetime) else value if isinstance(value, date) else None
    return None


_PRONOUN_LEAD = re.compile(r"(?:he|she|it) (?=(?:is|was|will|has)\b)", re.I)
_WEEKDAY_ONLY = re.compile(r"^(?:on |this |next )?(?:mon|tues|wednes|thurs|fri|satur|sun)day$", re.I)


#: Where a line written without full stops runs one thing into the next:
#: "landlord called back, plumber is coming thursday between 8 and 10".
_CLAUSE_SPLIT = re.compile(r"(,\s+|\s+and\s+|(?<=[.!?])\s+(?=[a-z]))")
#: A clause with a verb of its own is a thing that can be dated apart from
#: its neighbours; "Tuesday" or "3pm" after a comma, or the 10 of "between 8
#: and 10", is a detail of the last one.
_HAS_VERB = re.compile(r"\b(?:is|are|was|were|will|has|have|had|am|be|need|needs|needed|want|wants|must|should|got|get|gets|due|booked)\b|\b[a-z]{3,}(?:ed|ing)\b", re.I)
#: A feeling ("feeling pretty tired today") says how the writer is, not what is to be done, even when "today" dates it.
_MOOD = re.compile(r"^\W*(?:i(?:'|’)?m |i am |im )?(?:feeling|feel|felt|so|really|very|pretty)\b", re.I)


def _clauses(sentence: str) -> list[str]:
    """A sentence in the clauses that each have a verb; one with no such split stays whole."""
    parts = _CLAUSE_SPLIT.split(sentence)
    clauses: list[str] = []
    for text, joint in zip(parts[0::2], [*parts[1::2], ""]):
        if clauses and not _HAS_VERB.search(text):
            clauses[-1] += text + joint
        elif text.strip():
            clauses.append(text + joint)
        elif clauses:
            clauses[-1] += joint
    clauses = [c.strip().rstrip(",") for c in clauses]
    return clauses if len(clauses) > 1 else [sentence]


def _dated_lines(content: str):  # noqa: ANN202
    for line in content.splitlines():
        if line.strip() and not _DONE.match(line) and recognise_questions.dated_sentence(line) and not line.lstrip().startswith(("```", ">")):
            for sentence in _SENTENCE.split(line):
                if recognise_questions.dated_sentence(sentence):
                    yield from (c for c in _clauses(sentence) if recognise_questions.dated_sentence(c) and not _MOOD.match(c))


#: Reading a note's dates costs the recogniser; the same note is asked about
#: again by every plan, due and countdown turn. Keyed by the note's id, a hash
#: of its text and the day it was written, so an edit is a new key. Holds the
#: days of every dated sentence, whatever window is asked about later.
_DAYS_CACHE: dict[tuple, tuple[tuple[date, str], ...]] = {}
_CACHE_MAX = 1200


def _not_due(sentence: str, title: str) -> bool:
    """A day gone ("Wednesday bench 60kg." in a gym log, E20) or a habit ("Gym on Monday, Wednesday and Friday",
    bt-compcomp-1109 item 8): neither is a day that falls due."""
    return bool(recognise_questions.logged_day(sentence, title) or recognise.recurring_schedule(sentence))


def _sentence_case(text: str) -> str:
    """A clause lifted out of a line written in lower case: a capital to open it and on its weekdays."""
    text = re.sub(r"\b(mon|tues|wednes|thurs|fri|satur|sun)day\b", lambda m: m.group(0).capitalize(), text)
    return text[:1].upper() + text[1:]


def _note_days(note: dict, now: datetime) -> tuple[tuple[date, str], ...]:
    content = str(note.get("content") or "")
    anchor = _anchor(note, now)
    key = (note.get("id"), hash(content), anchor)
    hit = _DAYS_CACHE.get(key)
    if hit is not None:
        return hit
    found: list[tuple[date, str]] = []
    title = study.title_of(content)
    for sentence in _dated_lines(content):
        if _not_due(sentence, title):
            continue
        if recognise_questions.told_as_past(sentence) and not re.search(r"\d{4}", sentence):
            #: "Slept badly on Tuesday." happened; its day is never ahead (Z26).
            continue
        day = _sentence_day(sentence, anchor)
        text = _plain(sentence.lstrip("# ") if sentence.strip().startswith("#") else sentence)
        #: "He is coming Wednesday" in the note titled "Plumber" is "Plumber is coming Wednesday" (R9-6).
        lead = _PRONOUN_LEAD.match(text)
        if lead and title and len(title.split()) <= 4 and not title.endswith("…"):
            text = f"{title} {text[lead.end():]}"
        if day is not None and 3 <= len(text) <= 160:
            found.append((day, _sentence_case(text)))
    if len(_DAYS_CACHE) >= _CACHE_MAX:
        _DAYS_CACHE.clear()
    _DAYS_CACHE[key] = tuple(found)
    return _DAYS_CACHE[key]


def _note_events_of(note: dict, now: datetime, start: date, end: date) -> list[Event]:
    title = study.title_of(str(note.get("content") or ""))
    shown = composer_frame.name_of(note)
    return [Event(day, text, "note", note.get("id"), title, shown=shown) for day, text in _note_days(note, now) if start <= day <= end]


def note_events(ctx: Ctx, start: date, end: date) -> list[Event]:
    """The dated sentences of the notes that fall in [start, end]."""
    out: list[Event] = []
    for note in ctx.notes[:400]:
        if recognise_questions.dated_sentence(str(note.get("content") or "")):
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


def _grouped(found: list[Event], today: date, limit: int = MAX_ITEMS, *, headed: bool = True) -> list[str]:
    """The items under a bold day heading each; `headed=False` for one day the answer's own head already names (W8B
    1111: "For Wednesday 11 November you have ..." then "**Wednesday 11 November**" said the day twice)."""
    lines: list[str] = []
    shown = 0
    last = None
    for ev in found:
        if shown >= limit:
            break
        if ev.day != last:
            lines += ["", f"**{_name(ev.day, today)}**"] if headed else [""]
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


_WEEKDAYS = ("mon", "tues", "wednes", "thurs", "fri", "satur", "sun")


def _habit_events(ctx: Ctx, day: date) -> list[Event]:
    """The habits of the notes ("Gym on Monday, Wednesday and Friday at 7am", "every Tuesday") that fall on `day`,
    for a question about that one day: a habit is no deadline in a week's list, but it is on its days (W8 B14)."""
    name = re.compile(rf"\b{_WEEKDAYS[day.weekday()]}day|\bevery (?:other )?day\b|\bdaily\b", re.I)
    out: list[Event] = []
    for note in ctx.notes[:400]:
        content = str(note.get("content") or "")
        if not recognise_questions.dated_sentence(content):
            continue
        title = study.title_of(content)
        for sentence in _dated_lines(content):
            if recognise.recurring_schedule(sentence) and not recognise_questions.logged_day(sentence, title) and name.search(sentence):
                text = _plain(sentence)
                if 3 <= len(text) <= 160:
                    out.append(Event(day, text, "note", note.get("id"), title))
    return out


def _due(ctx: Ctx, win: tuple[date, date, str]) -> Reply | None:
    start, end, said = win
    today = ctx.now.date()
    found, overdue = events(ctx, start, end)
    if start == end:
        found = [*found, *(h for h in _habit_events(ctx, start) if h.text not in {e.text for e in found})]
    span = _range_words(start, end, said, today)
    if not found and not overdue:
        # The reminders path answers an empty window: it names a waiting
        # reminder outside it, or the next day the notes give
        # (tests/test_due_in_ask_1018.py). A window it does not know (a
        # weekday, "the next 7 days") has no such path, so it is said here.
        return None if recognise.ahead_window(said) else _nothing_due(ctx, end, span)
    head = compose.frame("due", ctx.mood, count=realise.counted(len(found), "dated item"), span=span) if found \
        else compose.frame("due_overdue", ctx.mood, span=span)
    head = compose.sentence_case(head)
    lines = [head, *_grouped(found, today, headed=start != end)]
    if overdue:
        lines += ["", "**Overdue**"] + [e.line(overdue=True) for e in overdue[:5]]
    if (end - start).days >= 3:
        lines += _next_reminder(ctx, end, found)
    return Reply("\n".join(lines), asks=[*_item_chips(found, today), *(["Plan my week"] if (end - start).days >= 3 else [])])


def _item_chips(found: list[Event], today: date) -> list[str]:
    """The Next chips an answer's own items give (audit 1028 E67): open the
    first note listed, and set a reminder for the first dated note line. Each
    is a sentence the app acts on; a reminder item already is one."""
    shown = found[:MAX_ITEMS]
    named = next((e for e in shown if e.kind == "note" and e.note_id is not None and _chip_title(e.title)), None)
    if named is None:
        return []
    title = _chip_title(named.title)
    when = "today" if named.day == today else "tomorrow" if named.day == today + timedelta(days=1) else f"on {named.day.day} {named.day:%B}"
    return [f"Open the {title} note", f"Remind me about {title} {when}"]


def _chip_title(title: str) -> str:
    """A note's name as a chip says it, or "" when it is cut short or holds a
    mark the ask would trip on."""
    title = " ".join((title or "").split())
    return "" if not title or title.endswith("…") or len(title) > 40 or re.search(r"[\"“”‘’\[\]#]", title) else title


#: What goes on from "Nothing is overdue." or an empty reminders count (F5).
AHEAD_CHIPS = ["What's due this week?", "What's due next week?"]


def _overdue(ctx: Ctx) -> Reply:
    """The reminders past their day, oldest first; nothing else."""
    late = sorted(_reminder_events(ctx, ctx.now.date(), ctx.now.date())[1], key=lambda e: (e.day, e.at))
    if not late:
        return Reply("Nothing is overdue.", asks=AHEAD_CHIPS)
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
        said_day = f"{_long(later[0].day)} {later[0].day.year}"
        line = compose.sentence_case(compose.frame("next_due", ctx.mood, what=later[0].text.rstrip(". "), when=said_day))
        #: "Deadline: Monday 16 November 2026 for the launch (Monday 16 November 2026)" says the day twice.
        lines += ["", line.replace(f" ({said_day})", "") if said_day.lower() in later[0].text.lower() else line]
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
            day = _sentence_day(task, _anchor(note, ctx.now)) if recognise_questions.dated_sentence(task) else None
            if day is not None and start <= day <= end:
                continue
            out.append((task, note, day is not None))
            if len(out) >= OPEN_LIMIT:
                return out
    return out


def _busiest(found: list[Event], days: list[date], load: dict) -> str:
    busiest = max(days, key=lambda d: (load[d], -days.index(d)))
    free = [d for d in days if load[d] == 0 and d.weekday() < 5]
    #: One item is not a busy day (audit 1030 Z57: "Busiest day: Saturday with 1").
    said = f"Busiest day: {_long(busiest)}, with {realise.count_word(load[busiest])} items." if load[busiest] > 1 else ""
    return " ".join(s for s in (said, f"Free weekdays: {', '.join(f'{d:%A}' for d in free)}." if free else "") if s)


def _task_groups(tasks: list) -> list[str]:
    lines: list[str] = []
    for heading, rows in (("Open tasks with no day", [t for t in tasks if not t[2]]), ("Open tasks dated outside this time", [t for t in tasks if t[2]])):
        if rows:
            lines += ["", f"**{heading} ({len(rows)})**"]
            lines += [f"- {task} ([{composer_frame.name_of(note)}](#/notes/{note['id']}))" for task, note, _d in rows]
    return lines


def _units(undated: list) -> list[str]:
    """The open items grouped by their note, as one errand each: a shopping
    list is one trip, not four (audit 1030 Z57). A note's one item is said
    as itself, more as the note's title and how many."""
    by_note: dict[int, list] = {}
    for task, note, _d in undated:
        by_note.setdefault(note["id"], [note]).append(task)
    return [rows[1] if len(rows) == 2 else f"{composer_frame.name_of(rows[0])} ({len(rows) - 1})" for rows in by_note.values()]


def _spread_line(undated: list, days: list[date], load: dict) -> list[str]:
    """Each note's items on the lightest day, a day taking a second note only
    once every day has one; the weekdays when two or more are left, else
    every day (a Friday's "this week" is Friday to Sunday)."""
    weekdays = [d for d in days if d.weekday() < 5]
    work = weekdays if len(weekdays) > 1 else days
    placed: dict[date, list[str]] = {}
    for unit in _units(undated):
        day = min(work, key=lambda d: (load[d] + len(placed.get(d, ())), len(placed.get(d, ())), d))
        placed.setdefault(day, []).append(unit)
    said = "; ".join(f"{d:%A}: {', '.join(u)}" for d, u in sorted(placed.items()))
    if len(placed) == 1:
        day, units = next(iter(placed.items()))
        return ["", f"{day:%A} is the lightest day for {', '.join(units)}."]
    return ["", f"A way to spread them over the lighter days: {said}."]


def _task_lines(tasks: list, days: list[date], load: dict) -> list[str]:
    lines = _task_groups(tasks)
    undated = [t for t in tasks if not t[2]]
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
    lines = [compose.sentence_case(compose.frame("plan", ctx.mood, span=span))]
    lines += _grouped(found, today, limit=10) if found else ["", "Nothing is dated in that time."]
    if overdue:
        lines += ["", "**Overdue**"] + [e.line(overdue=True) for e in overdue[:4]]
    if len(days) > 1 and found and (busy := _busiest(found, days, load)):
        lines += ["", busy]
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
    return f" From {('[' + (ev.shown or ev.title) + '](#/notes/' + str(ev.note_id) + ')') if ev.title else 'your note'}."


def _until(ctx: Ctx, subject: str) -> Reply | None:
    wanted = _stems(subject) - _FILLER_STEMS
    if not wanted:
        return None
    today = ctx.now.date()
    far = today + timedelta(days=900)
    found, _o = events(ctx, today, far)
    #: The shared ranker orders the events by their note (audit 1029 rank 18):
    #: the note titled as the subject, then the one that defines it, keep
    #: their place; reminders and the rest stay in date order.
    by_id = {n.get("id"): n for n in ctx.notes}
    found = note_rank.lead_by(found, subject, lambda e: by_id.get(e.note_id) or {"content": ""})
    ev = _event_counting_down_to(found, wanted, today)
    if ev is None:
        #: Said, not left to the search: "tax return" held by no note is a missing day, not a missing topic.
        #: A date or holiday as the subject ("12 Dec", "christmas") is the calculator's, not a missing note.
        from tessellate.ai import composer_calc

        dated = composer_calc._resolve(subject, today) is not None  # noqa: SLF001
        if not dated and not any(wanted <= _stems(n.get("content") or "") for n in ctx.notes):
            return Reply(f"I found no day for {subject.strip()} in your notes, so I cannot count down to it.")
        return None
    days = (ev.day - today).days
    lead = pick(ctx.seed, "until", (
        f"{compose.sentence_case(subject.strip())} is {_days_away(days)} away, on {_long(ev.day)}." if days > 1 else f"{compose.sentence_case(subject.strip())} is {_days_away(days)}, {_long(ev.day)}.",
        f"{_long(ev.day)} is when it falls, which is {_days_away(days)} from today." if days > 1 else f"That falls {_days_away(days)}: {_long(ev.day)}.",
    ))
    return Reply(f"{lead}{_until_source(ev)}\n\n“{ev.text}”")


def _plan_window(text: str, said: str, today: date) -> tuple[date, date, str]:
    win = window(said, today) or window(text, today)
    if win is not None and win[1] >= today:
        return win
    low = said.lower()
    if any(w in low for w in ("day", "today", "first", "focus", "start")):
        return today, today, "today"
    #: A weekend's "my week" is the coming seven days, as `window` reads "this
    #: week" there (audit 1031 C50).
    end = today + timedelta(days=6 - today.weekday())
    return today, end if (end - today).days > 1 else today + timedelta(days=6), "this week"


#: **One window for "what is due" with no time named** (audit 1030 Z27: "due
#: soon" said two weeks, "coming up" seven days, over different items). Both
#: readers take it from here: `composer_lists.window_of` too.
AHEAD_DAYS = 14
AHEAD_SAID = "the next two weeks"


def ahead_default(today: date) -> tuple[date, date, str]:
    """Today to two weeks on: "soon", "coming up", "what's on my plate"."""
    return today, today + timedelta(days=AHEAD_DAYS - 1), AHEAD_SAID


_KIND_STEMS = {study.stem(k) for k in _KINDS}


def _kind_due(ctx: Ctx, kinds: set[str], today: date) -> Reply | None:
    """"Any birthdays coming up": the dated lines about that kind, nearest first, as far as a year on (R9-8)."""
    found, _overdue = events(ctx, today, today + timedelta(days=366))
    kept = [e for e in found if kinds & _stems(e.text)]
    if not kept:
        return None
    noun = next(k for k in _KINDS if study.stem(k) in kinds)
    head = f"{len(kept)} {noun}{'s' if len(kept) != 1 else ''} ahead in your notes:"
    return Reply("\n".join([head, *_grouped(kept, today)]), asks=_item_chips(kept, today))


def _subject_stems(text: str, win) -> set[str]:  # noqa: ANN001
    """The stems of a due question that are not its window: what is left is its subject."""
    leftover = {s for s in _stems(re.sub(r"[^\w\s']", " ", _SPAN_WORDS.sub(" ", text))) if s not in _FILLER_STEMS}
    if win is not None:
        #: The window's own words, said as the question did ("before Christmas": a holiday is no subject here).
        for phrase in [*(p for _s, _e, p in when_words.find(text.lower())), win[2]]:
            leftover -= _stems(phrase)
    #: The know-ahead shape has nothing after its day: "my notes say" is not a subject.
    return set() if _KNOW_AHEAD.match(text) else leftover


def _due_reply(ctx: Ctx, text: str, today: date) -> Reply | None:
    win = window(text, today)
    leftover = _subject_stems(text, win)
    kind = {k for k in leftover if k in _KIND_STEMS}
    if kind and leftover == kind and not ctx.open_ids:
        return _kind_due(ctx, kind, today)
    if leftover or (win is None and ctx.open_ids):
        return None  # a subject, or "what is the deadline?" with a note open: the notes' (composer_open)
    return _due(ctx, win or ahead_default(today))


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
    return _not_done_later(ctx, out[:limit])


def _not_done_later(ctx: Ctx, tasks: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Leaves out an unticked line a later note records as done: "what is
    still open" agrees with "is X still on my list" (fable-eye F15). The
    notes are read only when there is an open line to check."""
    if not tasks:
        return tasks
    from tessellate.ai.composer_read import read_note  # noqa: PLC0415

    views = [v for i, n in enumerate(ctx.notes[:300]) if (v := read_note(n, i))]
    by_id = {v.note.get("id"): v for v in views}
    done: set[tuple[object, str]] = set()
    for nid in {note.get("id") for _, note in tasks}:
        if view := by_id.get(nid):
            done |= {(nid, study.clean(re.sub(r"^\s*[-*]?\s*\[[ xX]\]\s*", "", s.text))) for s in view.sentences if composer_done.recorded_later(views, view, s)}
    return [(task, note) for task, note in tasks if (note.get("id"), task) not in done]


def _open_reminders(ctx: Ctx) -> list[dict]:
    rows = [r for r in ctx.reminders if isinstance(r.get("due_at"), datetime) and not r.get("done")]
    return sorted(rows, key=lambda r: r["due_at"])


def _reminder_line(r: dict, today: date) -> str:
    due = r["due_at"]
    late = ", overdue" if due.date() < today else ""
    return f"- {str(r.get('text') or '').strip()} ({_short(due.date())}, {due:%H:%M}{late})"


def _not_reminded(reminders: list[dict], tasks: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """A reminder and a checklist line with the same words are one thing to do (G14 b)."""
    said = {study.clean(str(r.get("text") or "")).lower() for r in reminders}
    return [(task, note) for task, note in tasks if study.clean(task).lower() not in said]


def _left(ctx: Ctx) -> Reply | None:
    if ctx.open_ids:
        return None  # with a note open, that note's own list (composer_open)
    today = ctx.now.date()
    reminders, tasks = _open_reminders(ctx), _open_tasks(ctx)
    tasks = _not_reminded(reminders, tasks)
    if not reminders and not tasks:
        return Reply(compose.say("left_none", ctx.mood))
    r = realise.counted(len(reminders), "reminder")
    t = realise.counted(len(tasks), "unticked checklist item")
    if not reminders or not tasks:
        #: Never a zero clause ("0 reminders and 6 unticked items"): what is open is said alone.
        only, n = (t, len(tasks)) if not reminders else (r, len(reminders))
        lines = [compose.sentence_case(f"{only} {'is' if n == 1 else 'are'} still open.")]
    else:
        lines = [compose.frame("left", ctx.mood, r=r, t=t)]
    if reminders:
        lines += ["", "**Reminders**"] + [_reminder_line(x, today) for x in reminders[:MAX_ITEMS]]
    if tasks:
        lines += ["", "**Open checklist items**"]
        lines += [f"- {task} ([{composer_frame.name_of(note)}](#/notes/{note['id']}))" for task, note in tasks]
    return Reply("\n".join(lines))


def _when_is(ctx: Ctx, subject: str) -> Reply | None:
    """"When is my exam": a reminder that names it first, then the note's own
    sentence. Left to the notes' reader when no reminder does."""
    wanted = _stems(subject) - _FILLER_STEMS - _LIGHT_STEMS
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
        lines.append(pick(ctx.seed, "whennote", PHRASES["when_note"]).format(title=seen.shown or seen.title, id=seen.note_id, text=seen.text))
    return Reply("\n\n".join(lines))


def _when_reply(ctx: Ctx, text: str) -> Reply | None:
    when = _WHEN_IS.match(text) or _WHEN_IS_ALT.match(text)
    if when:
        return _when_is(ctx, when.group("t"))
    if (doing := _WHEN_DO.match(text)):
        return _when_is(ctx, doing.group("t"))
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


#: "what do I know about tomorrow": a day that has not come holds no notes
#: written then; what the notebook knows of it is what is on it. Only a day
#: named relative to now, never a holiday or a month (those are topics, C3).
_KNOW_AHEAD = re.compile(
    rf"^{_LEAD}(?:what do i know|what can you tell me|tell me|anything|what have i got|what is there|what(?:'s|’s) there|what do my notes have|"
    r"what (?:do|does) my (?:notes?|notebook|diary|journal) (?:say|tell me|show|have))\s+"
    r"(?:about|on|for|regarding)\s+(?:the )?" + recognise.AHEAD_DAY_WORDS + r"\W*$", re.I)


def _asks_due(text: str, today: date) -> bool:
    """"What is due", or a bare span ("the next 7 days"), or "what's on" with a window."""
    if _KNOW_AHEAD.match(text):
        win = window(text, today)
        return win is not None and win[1] >= today
    if _DUE.match(text):
        return not lookback(text, today)
    win = window(text, today)
    return bool((_SPAN_WORDS.search(text) or _BUSY.match(text)) and win is not None and win[1] >= today and not _written_from(text, today))


#: "what is in my todo" names the note called Todo (R3-8), not the next two weeks' dated items.
_IN_TODO = re.compile(r"^(?:what(?:'s|’s| is| are)?|show me|read me)\s+(?:in|inside)\s+(?:my |the |our )?(?:to-?do|todo|to do)(?:\s+(?:list|note))?\W*$", re.I)


def answer(ctx: Ctx) -> Reply | None:
    text = " ".join((ctx.question or "").split())
    if not text or len(text) > 200 or _IN_TODO.match(text):
        return None
    #: "what's been happening" looks back: the activity recap's, not "nothing dated ahead".
    if question_noise.catching_up(text):
        return None
    if day := composer_event_verdict.day_question(text):
        #: "are we meeting on Tuesday" asks of the day: its list, led by Yes or by what is missing.
        reply = _answer_text(ctx, day)
        return reply and Reply(f"{composer_event_verdict.lead(text, reply.text)} {reply.text}", reply.offer, reply.asks)
    #: As typed first; then with the casual wrapper and text-speak off ("whats on tmrw", R9-8, R9-14).
    return _answer_text(ctx, text) or (_answer_text(ctx, spelled) if (spelled := rephrase(text)) and spelled != text else None)


def _answer_text(ctx: Ctx, text: str) -> Reply | None:
    #: "schedule a reminder" starts one; it is not a plan to lay out (INBOX 1668 a).
    if reminder_parser.canonical_ask(text) != text:
        return None
    today = ctx.now.date()
    if _BARE_ON.match(text):
        return _due(ctx, ahead_default(today))
    if _LEFT.match(text):
        return _left(ctx)
    if _OVERDUE.match(text):
        return _overdue(ctx)
    until = _UNTIL.match(text)
    if until and not recognise_questions.is_duration_of_doing(text):
        return _until(ctx, until.group("t"))
    if (reply := _when_reply(ctx, text)) is not None:
        return reply
    plan = _PLAN.match(text)
    if plan:
        return _plan_reply(ctx, text, plan, today)
    return _due_reply(ctx, text, today) if _asks_due(text, today) else None


def _plan_reply(ctx: Ctx, text: str, plan: re.Match, today: date) -> Reply | None:
    """The plan a `_PLAN` match asks for; None for a topic to organise, which is no week (L-chat-32)."""
    if _topic_target(plan):
        return None
    if plan.group("st") is not None:
        return _plan(ctx, ahead_default(today))
    if plan.group("imp") or plan.group("imp2"):
        return _plan(ctx, (today, today, "today"))
    return _plan(ctx, _plan_window(text, " ".join(g for g in plan.groups() if g) or "this week", today))
