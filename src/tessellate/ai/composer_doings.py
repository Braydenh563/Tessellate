"""How often, how many times and how much a person did a thing, read from the
lines that say they did it (audit 1030 Z23): "how often do I run" counted
the notes filed under running; "how many times did I run" quoted the plan.

A doing is a line told in the past that names the verb ("Ran 8 km on 17
October", "Felt really good after the run today"), on the day the line names
or, with none, the day its note was written. A plan ("Saturday long run") is
not a doing. A distance in the line is summed. A habit line that names the
thing and two or more weekdays ("Gym on Monday, Wednesday and Friday") says
how often when no doing is written down.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from tessellate.ai import composer, composer_lists, factgraph, realise, recognise

_SELF = r"(?:do|did|have|has|does) i"
_ASKS = (
    ("often", re.compile(rf"^how often {_SELF} (?P<v>[a-z]+)(?P<r>.*)$")),
    ("count", re.compile(rf"^how many times {_SELF} (?P<v>[a-z]+)(?P<r>.*)$")),
    ("count", re.compile(rf"^how many (?P<v>[a-z]+?)s {_SELF} (?:do|done|go on|gone on|have|had|log|logged|manage|managed)(?P<r>.*)$")),
    #: "How far" and "how many km" are `composer_money`'s measure sums.
    ("total", re.compile(rf"^how much {_SELF} (?P<v>[a-z]+)(?P<r>.*)$")),
)
#: The rest of the question is about writing, not doing: `composer_slots._often` counts notes.
_ABOUT = re.compile(r"^(?:write|wrote|written|note|post|journal|mention|talk|think)\b")
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_IN_MONTH = re.compile(r"\b(?:in|during|for|this)\s+(" + "|".join(_MONTHS) + r")\b")
_WEEKDAY = re.compile(r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)days?\b", re.I)
_FILLER = frozenset({"to", "the", "a", "an", "my", "go", "at", "in", "on", "for", "of", "this", "last", "do", "i"})


@dataclass(frozen=True)
class Done:
    day: date
    view: object
    sentence: object
    km: float | None
    #: "Ran twice" in a week's review is two doings on that note's day.
    times: int = 1
    #: Whether the line names its own day (or the note is only the day it was written).
    dated: bool = True


def _forms(verb: str) -> tuple[str, str, frozenset[str]]:
    """(lemma, past, every written form) of a verb: "run" is also "ran" and "running"."""
    lemma = verb[:-1] if verb.endswith("s") and not verb.endswith("ss") else verb
    past = participle = lemma + ("d" if lemma.endswith("e") else "ed")
    for lem, was, been in factgraph._IRREGULAR:  # noqa: SLF001
        if lemma in (lem, was.split()[0]):
            lemma, past, participle = lem, was.split()[0], been
    every = {lemma, past, participle, lemma + "s", lemma + "ing", lemma + lemma[-1] + "ing"}
    return lemma, past, frozenset(every)


def _object(rest: str) -> list[str]:
    """The thing done, from what follows the verb ("to the gym" is gym), its
    time words left out."""
    rest = _IN_MONTH.sub(" ", rest)
    return [w for w in re.findall(r"[a-z]+", rest) if w not in _FILLER and w not in _MONTHS and w not in ("month", "week", "year")]


def _month(rest: str, today: date) -> tuple[int, int] | None:
    """(year, month) a question names ("in October"): the latest one not after today."""
    m = _IN_MONTH.search(rest)
    if not m:
        return None
    month = _MONTHS.index(m.group(1)) + 1
    return (today.year if month <= today.month else today.year - 1, month)


def _day_of(view, s, today: date) -> date | None:  # noqa: ANN001
    named = [d for d, at in composer._days_named(view, today, "past") if s.start <= at < s.end]  # noqa: SLF001
    if not named:
        return view.written
    #: A log kept in one note: "Ran 8 km on 17 October" in a note begun on 3
    #: October is this 17 October, not last year's.
    day, wrote = named[0], view.written
    same = day.replace(year=wrote.year) if wrote and (day.month, day.day) != (2, 29) else day
    return same if day < same <= today else day


def _km(text: str) -> float | None:
    """The first length in the line, in kilometres: the recogniser reads the figure and its unit."""
    for dimension, metres, _unit, _at in recognise.measures(text):
        if dimension == "length":
            return metres / 1000
    return None


def _names(text: str, obj: list[str]) -> bool:
    stems = set(composer._words(text))  # noqa: SLF001
    return all(composer._holds(composer._stem(o), stems) for o in obj)  # noqa: SLF001


#: "the lab ran over", "ran out of milk": the verb in another sense is no run.
_IDIOM = re.compile(r"\b(?:ran|run|runs|running)\s+(?:over|out|into|late|short|across|through|off)\b", re.I)
_NUMBER_WORDS = {"once": 1, "twice": 2, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_HOW_MANY = re.compile(r"\b(?:(once|twice)|(\d{1,2}|two|three|four|five|six|seven|eight|nine|ten) times)\b", re.I)


def _times_in(text: str, forms: frozenset[str]) -> int:
    """How many times a line says the doing ("Ran twice", "ran 3 times"); 1 when it gives no count."""
    m = _HOW_MANY.search(text)
    if not m or not (forms & set(re.findall(r"[a-z]+", text[: m.start()].lower()))):
        return 1
    said = (m.group(1) or m.group(2)).lower()
    return int(said) if said.isdigit() else _NUMBER_WORDS.get(said, 1)


#: "This week I ran twice": a total over a stretch, not a doing on a day.
_PERIOD = re.compile(r"\b(?:this|last|past|each|every|per|a) (?:week|month|year|fortnight)\b|\bso far\b|\b(?:weekly|monthly)\b", re.I)
_CALENDAR_DAY = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:" + "|".join(m[:3] for m in _MONTHS) + r")[a-z]*\b|\b(?:" + "|".join(m[:3] for m in _MONTHS) + r")[a-z]*\s+\d{1,2}\b", re.I)


def _kept_under(view, forms: frozenset[str]) -> bool:  # noqa: ANN001
    """Whether the note is a log of the doing: its title, filing or tags name it ("Running log")."""
    head = set(composer._words(f"{getattr(view, 'title', '')} {view.note.get('category') or ''} {' '.join(map(str, view.note.get('tags') or []))}"))  # noqa: SLF001
    return bool(forms & head)


def doings(views: list, forms: frozenset[str], obj: list[str], today: date) -> list[Done]:
    """Every line that says the doing was done, oldest first: a line told in
    the past that names the verb, and a dated line of a note kept as a log of
    it ("17 October: 8 km in 46 minutes" under "Running log"). One doing a
    day, except a line that counts them ("Ran twice")."""
    found: dict[tuple[date, int], Done] = {}
    for view in views:
        logged = _kept_under(view, forms)
        for s in view.sentences:
            words = set(re.findall(r"[a-z]+", s.text.lower()))
            #: "Ran twice, prepared the beta and booked nothing": the count settles the tense.
            says = bool(forms & words) and (recognise.told_as_past(s.text) or (_times_in(s.text, forms) > 1 and not _PERIOD.search(s.text))) and not _IDIOM.search(s.text)
            #: A log's line needs a day of its own and a figure; a plan has neither or is ahead.
            logs = logged and not says and _CALENDAR_DAY.search(s.text) and _km(s.text) is not None
            if not (says or logs) or not _names(s.text, obj):
                continue
            day = _day_of(view, s, today)
            if day is None or day > today:
                continue
            times = _times_in(s.text, forms) if says else 1
            own = day != view.written or bool(logs) or bool(re.search(r"\b(?:today|yesterday|tonight|this morning)\b", s.text, re.I))
            key = (day, 0 if times == 1 else s.start)
            if times == 1 and any(k[0] == day for k in found):
                continue
            found[key] = Done(day, view, s, _km(s.text), times, own)
    return sorted(found.values(), key=lambda d: d.day)


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{realise.count_word(n)} times")


def _days_said(done: list[Done]) -> str:
    said = [f"{d.day.day} {d.day:%B}" + (f" ({d.km:g} km)" if d.km else "") + (f" ({_times(d.times)})" if d.times > 1 else "") for d in done]
    return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1]


def _lead(shape: str, did: str, done: list[Done], span: str) -> str:
    days = len(done)
    n = sum(d.times for d in done)
    total = sum(d.km or 0 for d in done)
    if shape == "total" and total:
        return f"You {did} {total:g} km{span}, on {_days_said(done)}." if days == 1 else f"You {did} {total:g} km in all{span}, over {realise.count_word(days)} days: {_days_said(done)}."
    line = f"You {did} {_times(n)}{span}, on {_days_said(done)}"
    if shape == "often" and days > 1:
        gap = round((done[-1].day - done[0].day).days / (days - 1))
        line += f", about every {composer_lists._plural(max(gap, 1), 'day')}"  # noqa: SLF001
    return line + "."


def _habit(views: list, obj: list[str]):  # noqa: ANN202
    """(view, sentence) of a line that names the thing and two or more weekdays."""
    for view in sorted(views, key=lambda v: v.rank):
        for s in view.sentences:
            if obj and _names(s.text, obj) and len(_WEEKDAY.findall(s.text)) > 1:
                return view, s
    return None


def _source(view) -> str:  # noqa: ANN001
    title = composer_lists._title(view)  # noqa: SLF001
    return f"your {title} note" if getattr(view, "titled", False) and title[:1].isupper() else title


def _say_habit(out, views: list, obj: list[str], shape: str) -> bool:  # noqa: ANN001
    """How often by the habit line; asked how many times, first that no line logs each one."""
    got = _habit(views, obj)
    if got is None:
        return False
    view, s = got
    days = [d.capitalize() for d in _WEEKDAY.findall(s.text)]
    line = f"{realise.count_word(len(days))} times a week: {', '.join(days[:-1])} and {days[-1]}, going by {_source(view)}."
    line = line[:1].upper() + line[1:] if shape == "often" else f"Your notes do not log each time; the plan is {line}"
    out.lines.append(line)
    composer_lists._cite(out, view, s, line)  # noqa: SLF001
    return True


def asked(text: str) -> tuple[str, str, str] | None:
    """(shape, verb, rest) for a how-often, how-many-times or how-much question about a doing."""
    q = " ".join(text.lower().replace("?", " ").split())
    for shape, pattern in _ASKS:
        if (m := pattern.match(q)) and not _ABOUT.match(m.group("v")):
            return shape, m.group("v"), m.group("r")
    return None


def answer(out, text: str, views: list, today: date) -> bool:  # noqa: ANN001
    """Say how often, how many times or how much; False when the question is
    not one of these or no line says the doing."""
    got = asked(text)
    if got is None:
        return False
    shape, verb, rest = got
    _lemma, past, forms = _forms(verb)
    obj = _object(rest)
    done = doings(views, forms, obj, today)
    month = _month(rest, today)
    if month:
        done = [d for d in done if (d.day.year, d.day.month) == month]
    if shape == "total" and not any(d.km for d in done):
        return False  # "how much did I spend": a sum of money, `composer_money`'s
    if not done:
        return _say_habit(out, views, obj or [verb], shape)
    span = f" in {date(*month, 1):%B}" if month else ""
    did = past + (" " + " ".join(re.findall(r"[a-z]+", _IN_MONTH.sub(" ", rest))) if obj else "")
    line = _lead(shape, did.rstrip(), done, span)
    out.lines.append(line)
    for d in done:
        composer_lists._cite(out, d.view, d.sentence, line)  # noqa: SLF001
    return True
