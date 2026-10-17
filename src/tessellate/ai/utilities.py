"""Answers the app works out itself, with no note and no model (CHAT_PLAN
Phase 6, decision 41: the `computed` sentence, the third allowed kind beside
quoted and measured).

A sum, a unit or currency conversion, the time and the date, a count of days
to or from a date, a roll of a die. Each reads the question by a fixed
pattern, works the value out by rule (our own unit table, our own bounded
arithmetic in `arithmetic.py`, `when.span` for dates) and says it as one
sentence, followed by how the question was read ("Read as 5 miles in
kilometres."), so a misreading is visible rather than silent.

Nothing here reads a note and nothing leaves the computer: a currency answer
uses the dated table below and says its date (decision 43); the weather is
said to be something the app does not know.

`answer(question, now, salt)` returns the parts, `[(kind, text), ...]`, with
kind "computed" for a worked-out sentence and "phrase" for a fixed line of
`composer.PHRASES` (named by key), or None for a question that is not one of
these. `kind_of(question)` says which utility a question is, for the router.
"""

from __future__ import annotations

import functools
import hashlib
import re
import sys
from datetime import date, datetime

from tessellate.ai import arithmetic, recognise
from tessellate.ai import when as when_words

# --- units -----------------------------------------------------------------------

#: name -> (dimension, size in the dimension's base unit, the name said): the
#: recogniser's table (CHAT_PLAN decision 46), so a unit the chips read is a
#: unit this converts.
_UNITS = recognise.UNITS

_UNIT_NAMES = "|".join(sorted((re.escape(n) for n in _UNITS), key=len, reverse=True))
_NUM = r"(-?\d+(?:[.,]\d+)?)"
def _compile_convert() -> tuple:
    return (
    re.compile(rf"^(?:convert\s+)?{_NUM}\s*({_UNIT_NAMES})\s+(?:to|into|in|as)\s+({_UNIT_NAMES})$", re.I),
    re.compile(rf"^how many\s+({_UNIT_NAMES})\s+(?:is|are|in|make|makes|equals?)\s+(?:a|an|{_NUM})\s*({_UNIT_NAMES})$", re.I),
    re.compile(rf"^how (?:much|far|long|heavy|big|hot|cold) is\s+{_NUM}\s*({_UNIT_NAMES})\s+in\s+({_UNIT_NAMES})$", re.I),
    )

# --- currency (decision 43: a dated table, never fetched) ----------------------------

#: Units of each currency to one US dollar: approximate mid-market rates, set
#: by hand on `RATES_DATE` and said with every answer. A person who needs
#: today's rate knows from the date that this is not it.
RATES_DATE = date(2025, 6, 1)
RATES: dict[str, float] = {
    "USD": 1.0, "EUR": 0.88, "GBP": 0.74, "JPY": 144.0, "AUD": 1.55, "CAD": 1.37, "NZD": 1.67, "CHF": 0.82,
    "CNY": 7.19, "INR": 85.5, "SEK": 9.6, "NOK": 10.1, "DKK": 6.56, "SGD": 1.29, "HKD": 7.85, "MXN": 19.2,
    "BRL": 5.6, "ZAR": 17.9, "KRW": 1370.0, "PLN": 3.75,
}
_CURRENCY_NAMES = recognise.CURRENCY_NAMES
_MONEY_NAMES = "|".join(sorted((re.escape(n) for n in _CURRENCY_NAMES), key=len, reverse=True))
def _compile_money() -> tuple:
    return (
        re.compile(rf"^(?:convert\s+|how much is\s+|what is\s+)?({_MONEY_NAMES})?\s*{_NUM}\s*({_MONEY_NAMES})?\s+(?:to|into|in)\s+({_MONEY_NAMES})$", re.I),
    )


#: The two long patterns compile on first use (a few hundred unit names make
#: them the slowest part of importing the composer).
_PATTERNS: dict[str, tuple] = {}


def _patterns(name: str) -> tuple:
    if name not in _PATTERNS:
        _PATTERNS[name] = _compile_convert() if name == "convert" else _compile_money()
    return _PATTERNS[name]

# --- the clock, dates, chance ----------------------------------------------------------

_CLOCK = re.compile(r"^(?:what(?:'s| is) the time|what time is it|whats the time|the time|time)(?: now| right now)?$", re.I)
_TODAY = re.compile(
    r"^(?:what(?:'s| is) (?:the )?(?:date|day)(?: today| it)?|what day is it(?: today)?|what(?:'s| is) today(?:'s date)?|"
    r"today'?s date|what date is it(?: today)?|what(?:'s| is) the date today)$",
    re.I,
)
_YEAR = re.compile(r"^what (?:year|month) is it(?: now)?$", re.I)
#: "15% of 240" (CHAT_PLAN section 7 row 1: it quoted a note instead of 36).
_PERCENT = re.compile(r"^(?:what(?:'s| is)\s+|work out\s+|calculate\s+)?(-?\d+(?:\.\d+)?)\s*(?:%|percent|per cent)\s+of\s+(-?\d[\d,]*(?:\.\d+)?)$", re.I)
_WEEKDAY_OF = re.compile(r"^what day(?: of the week)? (?:is|was|will be|falls on) (\S.*)$", re.I)
_DIE = re.compile(r"^(?:roll|throw)\s+(?:a\s+|one\s+|the\s+)?(?:die|dice|d6)$|^roll\s+(\d{1,2})?d(\d{1,3})$", re.I)
_COIN = re.compile(r"^(?:flip|toss)\s+a\s+coin$|^heads or tails$", re.I)
_PICK = re.compile(r"^(?:pick|choose|give me)\s+a\s+(?:random\s+)?number\s+(?:between|from)\s+(-?\d{1,6})\s+(?:and|to)\s+(-?\d{1,6})$", re.I)
_WEATHER = re.compile(r"\b(?:weather|forecast|temperature outside|going to rain|will it rain)\b", re.I)
_TRANSLATE = re.compile(r"^(?:translate|say) \S.* (?:in|into|to) (?:french|spanish|german|italian|portuguese|dutch|japanese|chinese|korean|arabic|russian|hindi|greek|swedish|polish|turkish)$", re.I)

_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def _clean(question: str) -> str:
    text = " ".join(str(question or "").replace("?", " ").split()).strip(" .!")
    text = re.sub(r"^(?:hey|hi|ok|okay|so|please|can you|could you|tell me|do you know)[, ]+", "", text, flags=re.I)
    text = re.sub(r"^(?:can you |could you |please )?(?:tell me |work out |calculate )", "", text, flags=re.I)
    return re.sub(r"(?:,| |, )(?:please|thanks)$", "", text, flags=re.I).strip()


def _number(raw: str) -> float:
    return float(raw.replace(",", "."))


def _said(value: float) -> str:
    """A value to say: whole numbers whole, else to two places, never "-0"."""
    if abs(value) >= 1000:
        return f"{value:,.0f}" if abs(value - round(value)) < 0.05 else f"{value:,.1f}"
    if abs(value - round(value)) < 0.005:
        return str(int(round(value))) if round(value) else "0"
    return f"{value:.2f}".rstrip("0").rstrip(".") if abs(value) >= 0.01 else f"{value:.4g}"


def _day_words(day: date) -> str:
    return f"{_WEEKDAY_NAMES[day.weekday()]} {day.day} {_MONTH_NAMES[day.month - 1]} {day.year}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


_SINGULAR = {"inches": "inch", "feet": "foot", "stone": "stone"}


def _one(value: float, name: str) -> str:
    """A unit's name agreeing with its number: "1 litre", "2 litres"."""
    if _said(value) not in ("1", "-1") or name.startswith("°") or name == "K":
        return name
    head, _, rest = name.partition(" ")
    if name in _SINGULAR:
        return _SINGULAR[name]
    if head.endswith("s") and head not in ("US", "UK"):
        return " ".join(filter(None, (head[:-1], rest)))
    if head in ("US", "UK") and rest.endswith("s"):
        return f"{head} {rest[:-1]}"
    return name


def _temperature(value: float, src: str, dst: str) -> float:
    celsius = value if src == "°C" else (value - 32) * 5 / 9 if src == "°F" else value - 273.15
    return celsius if dst == "°C" else celsius * 9 / 5 + 32 if dst == "°F" else celsius + 273.15


def _convert(text: str) -> list[tuple] | None:
    for index, pattern in enumerate(_patterns("convert")):
        match = pattern.match(text)
        if not match:
            continue
        if index == 1:
            dst, raw, src = match.group(1), match.group(2) or "1", match.group(3)
        else:
            raw, src, dst = match.group(1), match.group(2), match.group(3)
        a, b = _UNITS[src.lower()] if src.lower() in _UNITS else _UNITS[src], _UNITS[dst.lower()] if dst.lower() in _UNITS else _UNITS[dst]
        if a[0] != b[0]:
            return [("computed", f"{a[2].capitalize()} and {b[2]} measure different things ({a[0]} and {b[0]}), so one does not convert to the other.")]
        value = _number(raw)
        result = _temperature(value, a[2], b[2]) if a[0] == "temperature" else value * a[1] / b[1]
        return [
            ("computed", f"{_said(value)} {_one(value, a[2])} is {_said(result)} {_one(result, b[2])}."),
            ("computed", f"\nRead as {_said(value)} {_one(value, a[2])} in {b[2]}."),
        ]
    return None


def _currency(text: str, rates: dict[str, float], rates_date: date) -> list[tuple] | None:
    for pattern in _patterns("money"):
        match = pattern.match(text)
        if not match:
            continue
        before, raw, after, dst = match.groups()
        src_name = (before or after or "").lower()
        if not src_name:
            return None
        src, target = _CURRENCY_NAMES.get(src_name), _CURRENCY_NAMES.get(dst.lower())
        if not src or not target or src not in rates or target not in rates:
            return None
        value = _number(raw)
        result = value / rates[src] * rates[target]
        when = f"{rates_date.day} {_MONTH_NAMES[rates_date.month - 1]} {rates_date.year}"
        return [
            ("computed", f"{_said(value)} {src} is about {_said(result)} {target} at the rates from {when}."),
            ("computed", f"\nRead as {_said(value)} {src} in {target}."),
        ]
    return None


def _salted(salt: str, text: str, low: int, high: int) -> int:
    digest = hashlib.sha1(f"{salt}|{text.lower()}".encode()).digest()
    return low + int.from_bytes(digest[:4], "big") % (high - low + 1)


def _dates(text: str, now: datetime) -> list[tuple] | None:
    today = now.date()
    asked = recognise.days_question(text)
    if asked and asked[0] == "future":
        found = when_words.span(asked[1], today, "future")
        if found is None:
            return None
        days = (found[0] - today).days
        if days < 0:
            return [("computed", f"{_day_words(found[0])} was {_plural(-days, 'day')} ago."), ("computed", f"\nRead as the days from today to {asked[1]}.")]
        return [
            ("computed", f"{_day_words(found[0])} is {_plural(days, 'day')} away." if days else "That is today."),
            ("computed", f"\nRead as the days from today to {asked[1]}."),
        ]
    if asked:
        found = when_words.span(asked[1], today, "past")
        if found is None:
            return None
        days = (today - found[0]).days
        return [("computed", f"{_day_words(found[0])} was {_plural(days, 'day')} ago."), ("computed", f"\nRead as the days from {asked[1]} to today.")]
    offset = recognise.offset_question(text)
    if offset:
        amount, unit, ago = offset
        phrase = f"{amount} {unit} ago" if ago else f"in {amount} {unit}"
        found = when_words.span(phrase, today, None)
        if found is None:
            return None
        return [("computed", f"{amount.capitalize() if not amount.isdigit() else amount} {unit} {'ago' if 'ago' in phrase else 'from today'} is {_day_words(found[0])}.")]
    match = _WEEKDAY_OF.match(text)
    if match:
        found = when_words.span(match.group(1), today, "future")
        if found is None or found[2] != "day":
            return None
        verb = "was" if found[0] < today else "is"
        which = "" if re.search(r"\d{4}", match.group(1)) else ", the next one from today"
        return [("computed", f"{found[0].day} {_MONTH_NAMES[found[0].month - 1]} {found[0].year} {verb} a {_WEEKDAY_NAMES[found[0].weekday()]}."),
                ("computed", f"\nRead as {match.group(1)}{which}.")]
    return None


def now_day() -> date:
    return date.today()


def until_subject(question: str) -> tuple[str, str] | None:
    """("future" or "past", the subject) of "how many days until the
    dentist", whose date only a note can give, or None."""
    text = _clean(question)
    asked = recognise.days_question(text)
    if asked:
        return asked[0], re.sub(r"^(?:the|my|our)\s+", "", asked[1].strip(), flags=re.I)
    return None


#: A sum said in words (CHAT_PLAN A1): "5 plus 5", "12 times 7", "100
#: divided by 4", "2 to the power of 8", read as its symbols, which the
#: answer's "Read as" line then shows.
_SAID_OPS = (
    (r"\bmultiplied by\b|\btimes\b", "*"), (r"\bdivided by\b|\bover\b", "/"), (r"\bplus\b|\badded to\b", "+"),
    (r"\bminus\b|\btake away\b", "-"), (r"\bto the power of\b|\bto the\b", "^"), (r"\bsquared\b", "^ 2"), (r"\bcubed\b", "^ 3"),
)


def _in_symbols(text: str) -> str:
    text = re.sub(r"^(?:how much is|what(?:'?s| is| does)|calculate|compute|work out)\s+", "", text, flags=re.I)
    text = re.sub(r" (?:equal|make|come to)$", "", " ".join(text.split()), flags=re.I)
    for words, symbol in _SAID_OPS:
        text = re.sub(words, symbol, text, flags=re.I)
    return text


def _sum_of(question: str, text: str) -> str | None:
    said = arithmetic.sum_in(question) or arithmetic.sum_in(text)
    if said:
        return said
    symbols = _in_symbols(text)
    return arithmetic.sum_in(symbols) if symbols != text and re.search(r"\d", symbols) else None


#: A list's average and friends (CHAT_PLAN A1): "average of 3, 8, 10",
#: "what's the median of 1, 5, 9 and 12", "add up 10, 20, 30".
_LIST_OF = re.compile(
    r"^(?:what(?:'?s| is) )?(?:the )?(?P<what>average|mean|median|sum|total|biggest|largest|smallest|max(?:imum)?|min(?:imum)?|range)"
    r"(?: number)? (?:of|in|for) (?P<nums>.+)$|^add (?:up |together )?(?P<add>.+)$",
    re.I,
)
_LIST_WORDS = {"average": "mean", "biggest": "largest", "max": "largest", "maximum": "largest", "smallest": "smallest", "min": "smallest", "minimum": "smallest", "total": "sum"}
_ROOT = re.compile(r"^(?:what(?:'?s| is) )?(?:the )?(square|cube) root of (-?\d+(?:\.\d+)?)$", re.I)
_MONTH_DAYS = re.compile(r"^how many days (?:are )?(?:there )?in (?P<month>[a-z]+)(?: (?P<year>\d{4}))?$", re.I)
_BORN = re.compile(r"^how old (?:is (?:someone|somebody|a person)|would i be|am i|are you)(?: if (?:i was|you were))? born in (?P<year>\d{4})$", re.I)
_CLOCK_SWAP = re.compile(
    r"^(?:what(?:'?s| is) )?(?P<time>\d{1,2}(?::\d{2})? ?(?:am|pm)?|noon|midnight) (?:in )?(?P<a>[a-z][a-z .'-]{1,40}?)(?: time)? (?:in|to|for) (?P<b>[a-z][a-z .'-]{1,40}?)(?: time)?$",
    re.I,
)


def _numbers(raw: str) -> list[float] | None:
    parts = [p for p in re.split(r"\s*(?:,|\band\b|\s)\s*", raw.strip()) if p]
    try:
        values = [float(p) for p in parts]
    except ValueError:
        return None
    return values if len(values) >= 2 else None


def _list_of(text: str) -> tuple[str, list[float]] | None:
    found = _LIST_OF.match(text)
    if not found:
        return None
    what = "sum" if found.group("add") else _LIST_WORDS.get(found.group("what").lower(), found.group("what").lower())
    values = _numbers(found.group("add") or found.group("nums"))
    return (what, values) if values else None


def _clock_swap(text: str) -> tuple | None:
    found = _CLOCK_SWAP.match(" ".join(text.split()))
    if not found:
        return None
    a, b = zone_for(found.group("a").strip()), zone_for(found.group("b").strip())
    return (found, a, b) if a and b else None


def _heard(question: str) -> str:
    """The question as the utilities read it: as typed when it is a utility,
    else with its misspellings put right ("the time in westen australia",
    INBOX 837), when that makes it one."""
    if _kind_of(question) is not None:
        return question
    from tessellate.ai import question_noise

    fixed = question_noise.repair(question)
    if fixed != question and _kind_of(fixed) is not None:
        return fixed
    #: One word a slip from a word a utility reads ("what tmie is it in
    #: japan", "concert 5 miles to km"), when that makes it one (O3). The
    #: patterns are anchored, so a real word is tried too; the weather words
    #: are not (`_WEATHER` is found anywhere), so they are not in the list.
    #: Three words at least: a bare "time" is the clock, so "home" or "Tom"
    #: alone would be read as it.
    if len(question.split()) < 3:
        return question
    guided = question_noise.guided(question, lambda t: _kind_of(t) is not None, _utility_words(), real_to=None)
    return guided or question


def _utility_words() -> frozenset[str]:
    """The words the utilities read: their own trigger words, every unit and
    currency name the recogniser has."""
    if not _UTILITY_WORDS:
        words = set(
            "what whats time date day year month today now convert how many much far long heavy roll throw die dice "
            "flip toss coin heads tails pick choose random number between percent calculate "
            "translate until days".split()
        )
        words.update(n.lower() for n in [*_UNITS, *_CURRENCY_NAMES] if n.isalpha() and len(n) >= 3)
        _UTILITY_WORDS.append(frozenset(words))
    return _UTILITY_WORDS[0]


_UTILITY_WORDS: list[frozenset[str]] = []


def kind_of(question: str) -> str | None:
    """Which utility `question` is, or None: the router's question, answered
    without working anything out."""
    return _kind_of(_heard(question))


def _kind_of(question: str) -> str | None:
    text = _clean(question)
    if not text:
        return None
    return _calculation_kind(question, text) or _date_kind(text) or _other_kind(text)


def _calculation_kind(question: str, text: str) -> str | None:
    if _sum_of(question, text):
        return "sum"
    if _list_of(text):
        return "list"
    if _ROOT.match(text):
        return "root"
    if _MONTH_DAYS.match(text) and _MONTH_DAYS.match(text).group("month").lower()[:3] in {m[:3].lower() for m in _MONTH_NAMES}:
        return "month_days"
    if _BORN.match(text):
        return "age"
    if _clock_swap(text):
        return "clock_swap"
    if _PERCENT.match(text):
        return "percent"
    if _is_clock(text):
        return "clock"
    if any(p.match(text) for p in _patterns("convert")):
        return "units"
    if any(p.match(text) for p in _patterns("money")):
        return "currency"
    return None


def _date_kind(text: str) -> str | None:
    asked = recognise.days_question(text)
    if asked:
        #: "how many days until the dentist": the date is in a note, which
        #: the composer reads (`composer._until_note`).
        return "dates" if when_words.span(asked[1], now_day(), asked[0]) else "until_note"
    if recognise.offset_question(text) or (_WEEKDAY_OF.match(text) and when_words.span(_WEEKDAY_OF.match(text).group(1), now_day(), "future")):
        return "dates"
    return None


def _other_kind(text: str) -> str | None:
    if _DIE.match(text) or _COIN.match(text) or _PICK.match(text):
        return "chance"
    if _TRANSLATE.match(text):
        return "translate"
    if _web_capability(text):
        return "web"
    if _WEATHER.search(text) and not re.search(r"\b(?:my|notes?|wrote)\b", text, re.I):
        return "weather"
    return None


# --- the time somewhere else (INBOX 801: "what's the time in western australia") ----

#: A place people name to the IANA zone that keeps its time. A city the zone
#: database names itself ("tokyo", "new york") needs no row: `zone_for` reads
#: the database's own city names. Rows are the regions, countries, states and
#: coasts it does not name, one zone each (a country with several takes its
#: capital's or its largest city's).
PLACE_ZONES: dict[str, str] = {
    "western australia": "Australia/Perth", "wa": "Australia/Perth", "south australia": "Australia/Adelaide",
    "northern territory": "Australia/Darwin", "queensland": "Australia/Brisbane", "qld": "Australia/Brisbane",
    "new south wales": "Australia/Sydney", "nsw": "Australia/Sydney", "victoria": "Australia/Melbourne",
    "tasmania": "Australia/Hobart", "canberra": "Australia/Sydney", "australia": "Australia/Sydney",
    "new zealand": "Pacific/Auckland", "nz": "Pacific/Auckland", "uk": "Europe/London",
    "united kingdom": "Europe/London", "england": "Europe/London", "britain": "Europe/London",
    "scotland": "Europe/London", "wales": "Europe/London", "ireland": "Europe/Dublin",
    "france": "Europe/Paris", "germany": "Europe/Berlin", "spain": "Europe/Madrid", "italy": "Europe/Rome",
    "netherlands": "Europe/Amsterdam", "holland": "Europe/Amsterdam", "portugal": "Europe/Lisbon",
    "greece": "Europe/Athens", "poland": "Europe/Warsaw", "sweden": "Europe/Stockholm", "norway": "Europe/Oslo",
    "switzerland": "Europe/Zurich", "russia": "Europe/Moscow", "turkey": "Europe/Istanbul",
    "egypt": "Africa/Cairo", "south africa": "Africa/Johannesburg", "nigeria": "Africa/Lagos", "kenya": "Africa/Nairobi",
    "uae": "Asia/Dubai", "india": "Asia/Kolkata", "delhi": "Asia/Kolkata", "new delhi": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "pakistan": "Asia/Karachi", "china": "Asia/Shanghai",
    "beijing": "Asia/Shanghai", "japan": "Asia/Tokyo", "korea": "Asia/Seoul", "south korea": "Asia/Seoul",
    "thailand": "Asia/Bangkok", "vietnam": "Asia/Ho_Chi_Minh", "indonesia": "Asia/Jakarta",
    "philippines": "Asia/Manila", "malaysia": "Asia/Kuala_Lumpur", "israel": "Asia/Jerusalem",
    "usa": "America/New_York", "us": "America/New_York", "america": "America/New_York",
    "united states": "America/New_York", "east coast": "America/New_York", "eastern time": "America/New_York",
    "washington dc": "America/New_York", "boston": "America/New_York", "miami": "America/New_York",
    "west coast": "America/Los_Angeles", "pacific time": "America/Los_Angeles", "california": "America/Los_Angeles",
    "la": "America/Los_Angeles", "san francisco": "America/Los_Angeles", "seattle": "America/Los_Angeles",
    "central time": "America/Chicago", "texas": "America/Chicago", "houston": "America/Chicago",
    "dallas": "America/Chicago", "mountain time": "America/Denver", "hawaii": "Pacific/Honolulu",
    "alaska": "America/Anchorage", "canada": "America/Toronto", "ontario": "America/Toronto",
    "british columbia": "America/Vancouver", "quebec": "America/Montreal", "mexico": "America/Mexico_City",
    "brazil": "America/Sao_Paulo", "argentina": "America/Argentina/Buenos_Aires", "buenos aires": "America/Argentina/Buenos_Aires",
    "chile": "America/Santiago", "peru": "America/Lima", "colombia": "America/Bogota",
    "utc": "UTC", "gmt": "UTC",
}

#: A country that keeps several mainland zones is answered with each, west to
#: east, rather than with its capital's alone (OPEN row 555: "the time in
#: Australia" said Sydney's, two hours out for Perth). A region the person
#: names ("western australia") keeps its one zone above.
SEVERAL_ZONES: dict[str, tuple[tuple[str, str], ...]] = {
    "australia": (("Perth", "Australia/Perth"), ("Adelaide", "Australia/Adelaide"),
                  ("Brisbane", "Australia/Brisbane"), ("Sydney", "Australia/Sydney")),
    "usa": (("Los Angeles", "America/Los_Angeles"), ("Denver", "America/Denver"),
            ("Chicago", "America/Chicago"), ("New York", "America/New_York")),
    "canada": (("Vancouver", "America/Vancouver"), ("Edmonton", "America/Edmonton"),
               ("Winnipeg", "America/Winnipeg"), ("Toronto", "America/Toronto"), ("Halifax", "America/Halifax")),
    "russia": (("Kaliningrad", "Europe/Kaliningrad"), ("Moscow", "Europe/Moscow"),
               ("Yekaterinburg", "Asia/Yekaterinburg"), ("Novosibirsk", "Asia/Novosibirsk"),
               ("Vladivostok", "Asia/Vladivostok")),
    "brazil": (("Manaus", "America/Manaus"), ("Sao Paulo", "America/Sao_Paulo")),
    "indonesia": (("Jakarta", "Asia/Jakarta"), ("Makassar", "Asia/Makassar"), ("Jayapura", "Asia/Jayapura")),
    "mexico": (("Tijuana", "America/Tijuana"), ("Mexico City", "America/Mexico_City"), ("Cancun", "America/Cancun")),
}
for _alias in ("us", "america", "united states", "united states of america"):
    SEVERAL_ZONES[_alias] = SEVERAL_ZONES["usa"]

_CLOCK_IN = re.compile(
    r"^(?:(?:(?:and|so) )?(?:what|how) about )?"
    r"(?:what(?:'s| is) the (?:current )?time|what time is it|whats the time|(?:the |current )?time)"
    r"(?: now| right now)? (?:in|at|over in) (?:the )?(?P<place>[a-z][a-z .'-]{1,40}?)(?: now| right now)?$",
    re.I,
)


@functools.lru_cache(maxsize=1)
def _zone_cities() -> dict[str, str]:
    """The zone database's own city names ("new york") to their zones; read
    once, since `available_timezones` walks the disk on every call."""
    from zoneinfo import available_timezones

    try:
        zones = available_timezones()
    except Exception:  # noqa: BLE001  # no zone database: only the table's places are read
        return {}
    return {z.rsplit("/", 1)[-1].replace("_", " ").lower(): z for z in sorted(zones) if "/" in z}


def place_name_for(place: str) -> str | None:
    """The name `zone_for` reads a place as: the table's or the zone
    database's own spelling, or the nearest one to a misspelling
    ("westen australia" is "western australia"), or None."""
    raw = " ".join(str(place or "").replace(".", "").split())
    key = raw.lower()
    if key in PLACE_ZONES or key in _zone_cities():
        return key
    if "/" in raw and raw in _zone_cities().values():
        return raw
    #: A misspelling is read only for a name of five letters or more, and only
    #: within one edit (two from nine letters; a swapped pair is one), so "wz"
    #: or "cat" never becomes a zone. A tie goes to the table, read first.
    #: Four letters only as a five-letter name with one letter dropped ("jaan"
    #: is japan, O3's slip test): never a change or an added letter.
    return _nearest_place(key) if len(key) >= 4 else None


def _nearest_place(key: str) -> str | None:
    """The place name `key` is a misspelling of, within its allowance."""
    allowed = 2 if len(key) >= 9 else 1
    best = None
    for name in (*PLACE_ZONES, *_zone_cities()):
        if len(name) < 5 or abs(len(name) - len(key)) > allowed or (len(key) == 4 and len(name) != 5):
            continue
        cost = _edits(key, name)
        if cost <= allowed and (best is None or cost < best[0]):
            best = (cost, name)
    return best[1] if best else None


def _edits(a: str, b: str) -> int:
    """Edits between two names: insert, delete, change, or swap two letters."""
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        row = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            row[j] = min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                row[j] = min(row[j], prev2[j - 2] + 1)
        prev2, prev = prev, row
    return prev[-1]


def zone_for(place: str) -> str | None:
    """The IANA zone for a place's name ("western australia", "Tokyo",
    "Europe/Paris", "westen australia"), or None."""
    name = place_name_for(place)
    if name is None:
        return None
    return PLACE_ZONES.get(name) or _zone_cities().get(name) or name


#: "what time is it in am/pm", "the time in 12 hour": the clock in the
#: 12-hour form (the owner, 2026-10-12: it could only say 18:53).
_TWELVE = re.compile(r"(?: (?:in|as|with|using))? (?:am ?/ ?pm|am ?pm|a\.m\.?/p\.m\.?|12-?h(?:ou)?r?(?: (?:time|clock|format))?)$", re.I)


def _twelve(text: str) -> tuple[str, bool]:
    #: Whitespace is collapsed first (linear) and the pattern uses single
    #: spaces, so there is no run of `\s` for it to backtrack over (CodeQL
    #: flagged the first form as a polynomial regular expression).
    squeezed = " ".join(text[:300].split())
    stripped = _TWELVE.sub("", squeezed)
    return stripped, stripped != squeezed


def _hm(moment: datetime, twelve: bool) -> str:
    return f"{moment.hour % 12 or 12}:{moment:%M} {'am' if moment.hour < 12 else 'pm'}" if twelve else f"{moment:%H:%M}"


def _is_clock(text: str) -> bool:
    text, _ = _twelve(text)
    if _CLOCK.match(text) or _TODAY.match(text) or _YEAR.match(text):
        return True
    match = _CLOCK_IN.match(text)
    return bool(match and zone_for(match.group("place")))


def _place_said(place: str) -> str:
    """"western australia" as "Western Australia", "wa" as "WA"."""
    words = place.split()
    return " ".join(w.upper() if len(words) == 1 and len(w) <= 3 else w[:1].upper() + w[1:] for w in words)


def _zone_said(there: datetime) -> str:
    """"AWST, UTC+8", "IST, UTC+5:30"; a zone with no letters of its own
    ("+04") is its offset alone."""
    offset = there.strftime("%z")
    hours, minutes = int(offset[1:3]), offset[3:]
    utc = "UTC" if offset[1:] == "0000" else f"UTC{offset[0]}{hours}{'' if minutes == '00' else ':' + minutes}"
    name = there.strftime("%Z")
    return utc if not name or name[0] in "+-" or name == "UTC" else f"{name}, {utc}"


def _where(place: str, zone: str) -> str:
    """The place as asked, with the city its clock is read from when that
    is not the same name ("Perth, Western Australia"; "Tokyo")."""
    said = _place_said(place)
    city = zone.rsplit("/", 1)[-1].replace("_", " ")
    return said if city.lower() in said.lower() or "/" not in zone else f"{city}, {said}"


def _other_day(there: datetime, now: datetime) -> str:
    here = now.date() if not now.tzinfo else now.astimezone().date()
    return "" if there.date() == here else f" on {_day_words(there.date())}"


def _clock(text: str, now: datetime) -> list[tuple]:
    text, twelve = _twelve(text)
    match = _CLOCK_IN.match(text)
    if match:
        from datetime import timezone
        from zoneinfo import ZoneInfo

        place = match.group("place").strip()
        several = SEVERAL_ZONES.get(" ".join(place.replace(".", "").lower().split()))
        if several:
            base = now if now.tzinfo else datetime.now(timezone.utc)
            times = ", ".join(f"{_hm(base.astimezone(ZoneInfo(z)), twelve)} in {city}" for city, z in several)
            return [("computed", f"{_place_said(place)} has several time zones. It is {times}."),
                    ("computed", "\nRead from this computer's clock; name a state or city for one of them.")]
        place = place_name_for(place) or place
        zone = zone_for(place)
        there = (now if now.tzinfo else datetime.now(timezone.utc)).astimezone(ZoneInfo(zone))
        return [("computed", f"It's {_hm(there, twelve)}{_other_day(there, now)} in {_where(place, zone)} ({_zone_said(there)})."),
                ("computed", f"\nRead as {zone}, from this computer's clock.")]
    if _CLOCK.match(text):
        return [("computed", f"It is {_hm(now, twelve)} on {_day_words(now.date())}."), _CLOCK_READ]
    if _YEAR.match(text):
        return [("computed", f"It is {_MONTH_NAMES[now.month - 1]} {now.year}."), _CLOCK_READ]
    return [("computed", f"Today is {_day_words(now.date())}."), _CLOCK_READ]


# --- asking whether the web can be searched (INBOX 801 and 808) -----------------------

_WEB_ASK = re.compile(
    r"\b(?:search|look (?:it |things )?up|google|browse|use|access|go)\b.*\b(?:the web|online|the internet|internet)\b|\bweb search\b",
    re.I,
)
_WEB_FILLER = re.compile(
    r"\b(?:can|could|would|will|do|does|are|is|you|u|please|search|look|up|it|things|stuff|google|browse|use|"
    r"access|go|on|in|the|web|online|internet|have|has|a|able|to|for|me|there|turned)\b|[?.!,]",
    re.I,
)


def web_on() -> bool:
    """The person's web search setting; off when there is none to read."""
    #: Read only when the app has loaded it: the composer runs without the
    #: database layer (`tests/test_question_noise.py`), and there it is off.
    deps = sys.modules.get("tessellate.core.deps")
    if deps is None:
        return False
    try:
        return bool(deps.get_config().get_preference("web_search_enabled", False))
    except Exception:  # noqa: BLE001  # no app state yet: off
        return False


def _web_capability(text: str) -> bool:
    """"can you search the web?" is a question about the app, answered
    plainly, never a notes search for the word "web" (INBOX 801, 808); with
    web search off, so is any request to search the web."""
    if not _WEB_ASK.search(text):
        return False
    return not _WEB_FILLER.sub(" ", text).split() or not web_on()


#: Decision 54: a computed sentence always says how the question was read.
#: A sum says its expression as the sentence's subject ("12 * 7 is 84."),
#: which is its reading; everything else carries a "Read as" line.
_CLOCK_READ = ("computed", "\nRead as the date and time on this computer's clock.")


def answer(question: str, now: datetime | None = None, salt: str = "", rates: dict | None = None, rates_date: date | None = None) -> list[tuple] | None:
    """The parts of a utility answer to `question`, or None."""
    question = _heard(question)
    kind = _kind_of(question)
    if kind is None or kind == "until_note":
        return None
    now = now or datetime.now()
    text = _clean(question)
    if kind == "sum":
        expr = _sum_of(question, text)
        value = arithmetic.spoken(arithmetic.evaluate(expr))
        read = " ".join(expr.replace("*", " × ").replace("/", " ÷ ").replace("^", " to the power of ").split())
        said = [("computed", f"{expr.strip()} is {value}.")]
        #: A sum typed in symbols is its own reading; one said in words is shown as read.
        return said if arithmetic.sum_in(question) or arithmetic.sum_in(text) else [*said, ("computed", f"\nRead as {read}.")]
    if kind == "list":
        return _list_answer(*_list_of(text))
    if kind == "root":
        which, raw = _ROOT.match(text).groups()
        number = float(raw)
        if which.lower() == "square" and number < 0:
            return None
        value = abs(number) ** (1 / 2 if which.lower() == "square" else 1 / 3) * (-1 if number < 0 else 1)
        return [("computed", f"The {which.lower()} root of {raw} is {_said(value)}."), ("computed", f"\nRead as the {which.lower()} root of {raw}.")]
    if kind == "month_days":
        return _month_days(_MONTH_DAYS.match(text), now)
    if kind == "age":
        year = int(_BORN.match(text).group("year"))
        if not 1900 <= year <= now.year:
            return None
        age = now.year - year
        return [("computed", f"{age} this year, or {age - 1} until their birthday."), ("computed", f"\nRead as the years from {year} to {now.year}.")]
    if kind == "clock_swap":
        return _swap_answer(*_clock_swap(text), now)
    if kind == "percent":
        share, whole = _PERCENT.match(text).groups()
        worked = arithmetic.evaluate(f"{share} / 100 * {whole.replace(',', '')}")
        return [("computed", f"{share}% of {whole} is {arithmetic.spoken(worked)}."),
                ("computed", f"\nRead as {share} hundredths of {whole}.")]
    if kind == "clock":
        return _clock(text, now)
    if kind == "units":
        return _convert(text)
    if kind == "currency":
        return _currency(text, rates or RATES, rates_date or RATES_DATE)
    if kind == "dates":
        return _dates(text, now)
    if kind == "chance":
        match = _PICK.match(text)
        if match:
            low, high = sorted((int(match.group(1)), int(match.group(2))))
            return [("computed", f"{_salted(salt, text, low, high)}."), ("computed", f"\nRead as a whole number from {low} to {high}, picked at random.")]
        if _COIN.match(text):
            return [("computed", f"{'Heads' if _salted(salt, text, 0, 1) else 'Tails'}."), ("computed", "\nRead as one coin toss, picked at random.")]
        match = _DIE.match(text)
        count = int(match.group(1) or 1) if match.group(2) else 1
        sides = int(match.group(2) or 6)
        if not (1 <= count <= 10 and 2 <= sides <= 100):
            return None
        rolls = [_salted(f"{salt}:{i}", text, 1, sides) for i in range(count)]
        said = f"You rolled {rolls[0]}." if count == 1 else f"You rolled {', '.join(map(str, rolls))}: {sum(rolls)} in all."
        dice = "one roll" if count == 1 else f"{count} rolls"
        return [("computed", said), ("computed", f"\nRead as {dice} of a {sides}-sided die, picked at random.")]
    if kind == "translate":
        return [("phrase", "utility_translate")]
    if kind == "web":
        return [("phrase", "utility_web_on" if web_on() else "utility_web_off")]
    return [("phrase", "utility_weather")]


def _list_answer(what: str, values: list[float]) -> list[tuple]:
    import statistics

    worked = {
        "mean": statistics.fmean, "median": statistics.median, "sum": sum,
        "largest": max, "smallest": min, "range": lambda v: max(v) - min(v),
    }[what](values)
    listed = ", ".join(_said(v) for v in values)
    name = {"mean": "average", "sum": "total"}.get(what, what)
    return [("computed", f"The {name} of {listed} is {_said(worked)}."),
            ("computed", f"\nRead as the {what} of {len(values)} numbers{', added and divided by ' + str(len(values)) if what == 'mean' else ''}.")]


def _month_days(found: re.Match, now: datetime) -> list[tuple] | None:
    import calendar

    month = next(i for i, m in enumerate(_MONTH_NAMES, 1) if m[:3].lower() == found.group("month").lower()[:3])
    year = int(found.group("year") or now.year)
    days = calendar.monthrange(year, month)[1]
    return [("computed", f"{_MONTH_NAMES[month - 1]} {year} has {days} days."), ("computed", f"\nRead as the days in {_MONTH_NAMES[month - 1]} {year}{', a leap year' if calendar.isleap(year) and month == 2 else ''}.")]


def _swap_answer(found: re.Match, a: str, b: str, now: datetime) -> list[tuple] | None:
    from zoneinfo import ZoneInfo

    raw = found.group("time").lower().replace(" ", "")
    clock = re.match(r"(\d{1,2})(?::(\d{2}))?(am|pm)?$", raw)
    if raw in ("noon", "midnight"):
        hour, minute = (12 if raw == "noon" else 0), 0
    elif clock:
        hour, minute = int(clock.group(1)), int(clock.group(2) or 0)
        if clock.group(3) == "pm" and hour < 12:
            hour += 12
        if clock.group(3) == "am" and hour == 12:
            hour = 0
    else:
        return None
    if hour > 23 or minute > 59:
        return None
    there = datetime(now.year, now.month, now.day, hour, minute, tzinfo=ZoneInfo(a))
    here = there.astimezone(ZoneInfo(b))
    day = "" if here.date() == there.date() else (" the next day" if here.date() > there.date() else " the day before")
    first, second = _place_said(found.group("a").strip()), _place_said(found.group("b").strip())
    return [("computed", f"{there:%H:%M} in {first} is {here:%H:%M}{day} in {second}."),
            ("computed", f"\nRead as {there:%H:%M} today in {a} ({there:%Z}), in {b} ({here:%Z}).")]


# --- a text's counts and outline (CHAT_PLAN section 2, the documents row) -------------
#
# One module for what the documents editor, the note composer, the Library's
# Contents index and the agent say about a text's size and shape, so a count
# is one number wherever it is shown. The browser's twin is `textCounts`
# (settings-wiring.js) and `docScanHeadings` (documents.js);
# `tests/test_text_utilities.py` holds all three to `wc` and to each other on
# one fixture.

#: Words a minute for "reading time": the rate the editor has always used.
READING_WPM = 220
_ATX = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
_SETEXT = re.compile(r"^\s*(=+|-{2,})\s*$")
_NOT_PARAGRAPH = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\|)")


def counts(text: str) -> dict:
    """Words, characters and lines as `wc -w`, `wc -m` and `wc -l` count them
    (a word is a run of non-space, a character a code point, a line a
    newline), and the reading time in minutes."""
    text = str(text or "")
    words = len(text.split())
    return {
        "words": words,
        "chars": len(text),
        "lines": text.count("\n"),
        "minutes": words / READING_WPM,
        "read": reading_time(words),
    }


def reading_time(words: int) -> str:
    """How the app says a reading time: "under a min", "4 min read", "1.5h read"."""
    if not words:
        return ""
    minutes = words / READING_WPM
    if minutes < 1:
        return "under a min"
    if minutes < 60:
        return f"{round(minutes)} min read"
    return f"{minutes / 60:.1f}h read"


def _heading_at(lines: list[str], index: int, found: list[dict], max_level: int) -> dict | None:
    """The heading the line at `index` closes or is, or None: a `#` line, or the
    `===`/`---` underline of a paragraph line above it."""
    line = lines[index]
    match = _ATX.match(line)
    if match:
        if match.group(2).strip() and len(match.group(1)) <= max_level:
            return {"line": index, "level": len(match.group(1)), "text": match.group(2).strip()[:200]}
        return None
    if index and _SETEXT.match(line):
        above = lines[index - 1]
        if above.strip() and not _NOT_PARAGRAPH.match(above) and not (found and found[-1]["line"] == index - 1):
            return {"line": index - 1, "level": 1 if line.strip()[0] == "=" else 2, "text": above.strip()[:200]}
    return None


def outline(text: str, max_level: int = 6, limit: int | None = None) -> list[dict]:
    """`{line, level, text}` for each heading, `line` zero-based: `#` headings
    to `max_level`, and the underlined (setext) form, as the editor draws
    them; a `#` inside a fenced block is code, not a heading."""
    found: list[dict] = []
    fenced = False
    lines = str(text or "").split("\n")
    for index, line in enumerate(lines):
        if line.strip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = _heading_at(lines, index, found, max_level)
        if heading is not None:
            found.append(heading)
        if limit and len(found) >= limit:
            break
    return found
