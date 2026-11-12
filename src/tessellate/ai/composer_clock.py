"""The calendar read off the clock, no note and no model (CHAT_PLAN T13):
"what week is it", "what quarter is it", "what day of the year is it",
"what's tomorrow's date", and (the Time and date row) "what week is 3 March",
"is 2028 a leap year", "how many days are left in the year".

`utilities.py` says the date and the time; this adds the next things people
ask the clock. Every answer is worked out from the turn's date and says how
it was read ("_Read as ..._"). Questions read with their blanks collapsed to
single spaces and no group starts at a blank, so each pattern is linear.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from tessellate.ai import recognise
from tessellate.ai.composer_study import Ctx, Reply

_WEEK_NOW = re.compile(
    r"^(?:(?:what|which) week (?:is it|are we in|is it now|is it today|number is it|of the year is it|of the year are we in)"
    r"|what is (?:the )?(?:current |this )?week(?: number)?(?: today| now)?|(?:current |this )?week number(?: today| now)?)$"
)
_QUARTER = re.compile(r"^(?:(?:what|which) quarter (?:is it|are we in|of the year is it)|what is (?:the )?current quarter|current quarter)$")
_YEAR_DAY = re.compile(
    r"^(?:(?:what|which) day of the year (?:is it|is today|is this)|what is (?:the )?day of the year(?: today| now)?|day of the year(?: today| now)?"
    r"|what is (?:the )?day number(?: today)?)$"
)
_WEEK_OF = re.compile(r"^(?:(?:what|which) week(?: number)?(?: of the year)? (?:is|was)|week number (?:of|for)) (?P<d>\S.*)$")
_YEAR_DAY_OF = re.compile(r"^(?:(?:what|which) day of the year (?:is|was)|what is (?:the )?day number of) (?P<d>\S.*)$")
#: A bare day and month ("3 march", "march 3rd"): in a week or day-of-year question that is this year, not the next time it comes round.
_BARE_DATE = re.compile(r"^(?:the )?(?:(?P<d>\d{1,2})(?:st|nd|rd|th)?(?: of)? (?P<m>[a-z]{3,9})|(?P<m2>[a-z]{3,9}) (?P<d2>\d{1,2})(?:st|nd|rd|th)?)(?: (?P<y>\d{4}))?$")
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_LEFT = re.compile(
    r"^(?:how many )?(?P<u>days|weeks)(?: are)? (?:left|remaining|remain|to go) (?:in|of) (?:the|this) year$"
    r"|^how many (?P<v>days|weeks) (?:until|till|to) (?:the )?(?:end of (?:the|this) year|year end)$"
)
_QUARTER_MONTHS = ("January to March", "April to June", "July to September", "October to December")


def long_day(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B %Y}"


def computed(said: str, read: str) -> Reply:
    return Reply(f"{said}\n\n_Read as {read}._")


def clean(question: str) -> str:
    """Lower case, single-spaced, no commas or closing punctuation, and
    "what's" as "what is"."""
    text = " ".join((question or "").replace(",", " ").lower().split()).rstrip(" ?.!")
    return re.sub(r"^(?:what's|whats) ", "what is ", text)


def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _week(today: date) -> Reply:
    iso = today.isocalendar()
    return computed(f"It is week {iso.week} of {iso.year}.", f"the ISO week number of {long_day(today)} (weeks start on Monday)")


def _quarter(today: date) -> Reply:
    q = (today.month - 1) // 3
    return computed(f"It is quarter {q + 1} of {today.year}, {_QUARTER_MONTHS[q]}.", f"the calendar quarter of {long_day(today)}")


def _year_day(today: date) -> Reply:
    total = 366 if is_leap(today.year) else 365
    n = today.timetuple().tm_yday
    left = total - n
    return computed(f"Today is day {n} of {today.year}, and {left} {'day remains' if left == 1 else 'days remain'}.",
                    f"day {n} of {total} for {long_day(today)}")


def _neighbour(which: str, today: date) -> Reply:
    if which == "tomorrow":
        day = today + timedelta(days=1)
        return computed(f"Tomorrow is {long_day(day)}.", "the day after today")
    day = today - timedelta(days=1)
    return computed(f"Yesterday was {long_day(day)}.", "the day before today")


def _this_year(phrase: str, today: date) -> date | None:
    """The date of a day and month (with a year if given, else `today`'s), else None."""
    found = _BARE_DATE.match(phrase)
    if not found:
        return None
    name = found["m"] or found["m2"]
    month = next((i for i, m in enumerate(_MONTHS, 1) if len(name) >= 3 and m.startswith(name)), 0)
    try:
        return date(int(found["y"] or today.year), month, int(found["d"] or found["d2"])) if month else None
    except ValueError:
        return None


def on(phrase: str, today: date) -> date | None:
    """The day a phrase names: a bare day and month is this year, else whatever `recognise` makes of it."""
    day = _this_year(phrase, today)
    if day is not None:
        return day
    got = recognise.resolve(phrase, datetime.combine(today, time(10)))
    return got.date() if got else None


def _year_day_of(phrase: str, today: date) -> Reply | None:
    day = on(phrase, today)
    if day is None:
        return None
    n = day.timetuple().tm_yday
    return computed(f"{long_day(day)} {'was' if day < today else 'is'} day {n} of {day.year}.", f"day {n} of {366 if is_leap(day.year) else 365} for {long_day(day)}")


def _week_of(phrase: str, today: date) -> Reply | None:
    day = on(phrase, today)
    if day is None:
        return None
    iso = day.isocalendar()
    return computed(f"{long_day(day)} {'was' if day < today else 'is'} in week {iso.week} of {iso.year}.",
                    f"the ISO week number of {long_day(day)} (weeks start on Monday)")


def _leap(which: str, today: date) -> Reply:
    year = int(which) if which.isdigit() else today.year + recognise.YEAR_SHIFT[which]
    verb = "was" if year < today.year else "is"
    if is_leap(year):
        return computed(f"{year} {verb} a leap year: it has 366 days, and February has 29.", "the leap year rule: every fourth year, except centuries not divisible by 400")
    return computed(f"{year} {verb} not a leap year: it has 365 days, and February has 28.", "the leap year rule: every fourth year, except centuries not divisible by 400")


def _left(unit: str, today: date) -> Reply:
    end = date(today.year, 12, 31)
    days = (end - today).days
    said = f"{days} {'day' if days == 1 else 'days'}" if unit == "days" else f"{round(days / 7, 1):g} weeks ({days} {'day' if days == 1 else 'days'})"
    return computed(f"There {'is' if said.startswith('1 day') else 'are'} {said} left in {today.year}, after today.",
                    f"the days from tomorrow to {long_day(end)}")


def answer(ctx: Ctx) -> Reply | None:
    text = clean(ctx.question)
    if not text or len(text) > 120:
        return None
    today = ctx.now.date()
    if _WEEK_NOW.match(text):
        return _week(today)
    if _QUARTER.match(text):
        return _quarter(today)
    if _YEAR_DAY.match(text):
        return _year_day(today)
    year = recognise.leap_year_asked(text)
    if year:
        return _leap(year, today)
    found = _LEFT.match(text)
    if found:
        return _left(found["u"] or found["v"], today)
    found = _YEAR_DAY_OF.match(text)
    if found:
        return _year_day_of(found["d"], today)
    found = _WEEK_OF.match(text)
    if found:
        return _week_of(found["d"], today)
    which = recognise.neighbour_day(text)
    if which:
        return _neighbour(which, today)
    return None
