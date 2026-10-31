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


def doings(views: list, forms: frozenset[str], obj: list[str], today: date) -> list[Done]:
    """Every line told in the past that names the doing, one per day, oldest first."""
    found: dict[date, Done] = {}
    for view in views:
        for s in view.sentences:
            words = set(re.findall(r"[a-z]+", s.text.lower()))
            if not (forms & words) or not _names(s.text, obj) or not recognise.told_as_past(s.text):
                continue
            day = _day_of(view, s, today)
            if day is not None and day <= today and day not in found:
                found[day] = Done(day, view, s, _km(s.text))
    return [found[d] for d in sorted(found)]


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{realise.count_word(n)} times")


def _days_said(done: list[Done]) -> str:
    said = [f"{d.day.day} {d.day:%B}" + (f" ({d.km:g} km)" if d.km else "") for d in done]
    return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1]


def _lead(shape: str, did: str, done: list[Done], span: str) -> str:
    n = len(done)
    total = sum(d.km or 0 for d in done)
    if shape == "total" and total:
        return f"You {did} {total:g} km{span}, on {_days_said(done)}." if n == 1 else f"You {did} {total:g} km in all{span}, over {realise.count_word(n)} days: {_days_said(done)}."
    line = f"You {did} {_times(n)}{span}, on {_days_said(done)}"
    if shape == "often" and n > 1:
        gap = round((done[-1].day - done[0].day).days / (n - 1))
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
