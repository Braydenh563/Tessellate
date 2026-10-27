"""Whether a model's words keep to the app's counts (CHAT_PLAN decision 75:
with a model up the model writes the answer from the engine's facts, and its
prose may not contradict them).

A count is a figure attached to a counted noun ("3 reminders", "no notes",
"one tag"), compared with the counts the engine itself produced: the totals
and row counts of the tool result or the statistic (`result_counts`,
`rows_counts`) and the counted statements of the engine's own lead sentence
(`said_counts`). A date ("Mon 2 Nov"), a time ("14:02", "at 9"), an id
("#/notes/12") are never counts, so a digit there can neither excuse a
miscount nor be one. A span ("120 minutes", "59 days", "8 weeks and 3 days")
is checked against the spans the facts state, in any unit and with the
rounding a person would use ("about 2 months"), and against the dates the
facts carry (`_dated_spans`); a span from neither is the model's invention.
"one", "no", "none", "nothing" and "zero" are figures like any other.
"""

from __future__ import annotations

import re
from datetime import datetime

from tessellate.ai import recognise

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
#: Said as nothing at all: a figure of zero standing on its own.
_NONE_WORDS = {"none", "nothing"}

#: The nouns a count is of, by the forms prose uses. "*" is a count of
#: anything ("three things are waiting"), checked against every count.
_NOUNS = {
    **dict.fromkeys(("note", "notes", "entry", "entries"), "note"),
    **dict.fromkeys(("reminder", "reminders", "task", "tasks", "to-do", "to-dos", "todo", "todos"), "reminder"),
    **dict.fromkeys(("tag", "tags"), "tag"),
    **dict.fromkeys(("category", "categories"), "category"),
    **dict.fromkeys(("document", "documents", "doc", "docs", "file", "files", "pdf", "pdfs"), "document"),
    **dict.fromkeys(("skill", "skills"), "skill"),
    **dict.fromkeys(("board", "boards"), "board"),
    **dict.fromkeys(("map", "maps"), "map"),
    **dict.fromkeys(("link", "links", "connection", "connections"), "link"),
    **dict.fromkeys(("thing", "things", "item", "items", "result", "results", "match", "matches"), "*"),
}
#: The tool whose result a bare total counts.
TOOL_NOUNS = {
    "list_reminders": "reminder", "list_tags": "tag", "list_categories": "category", "count_notes": "note",
    "list_notes": "note", "list_documents": "document", "list_skills": "skill",
}
_MONTHS = recognise.MONTH_NAMES
_WEEKDAYS = recognise.WEEKDAY_NAMES
#: After a figure, the word that makes it a time of day, never a count.
_CLOCK = {"am", "pm", "o'clock", "oclock"}
#: After a figure, the unit that makes it a span ("3 days", "120 minutes"),
#: in minutes. A span is read as (value, "~<minutes>") and checked only
#: against the spans the facts state and the dates they carry
#: (`_span_kept`, `_dated_spans`).
_SPAN_MINUTES = recognise.SPAN_MINUTES
#: Before a span, the word that says it is rounded: "roughly 60 days" may be
#: 5% off, "60 days" may not (`_span_kept`).
_HEDGES = {"about", "roughly", "almost", "nearly", "around", "approximately", "approx", "circa", "some", "over", "under", "~"}
#: Before a figure, the word that makes it a time or a place ("at 9", "#12").
_BEFORE_TIME = {"at", "#", "/", "no.", "number"}
#: Before a figure that counts nothing, the word that makes it a time ("due
#: Thursday by 10", "until 9.30"); "by 3 notes" still counts.
_BEFORE_CLOCK = {"by", "until", "till", "before", "after", "around"}
#: A figure that counts nothing and reads as a year ("October 28, 2026").
_YEAR = re.compile(r"(?:19|20)\d\d$")
#: Words that end the reach from a figure to its noun ("one of the notes"
#: does not say there is one note).
_STOPS = {"of", "is", "are", "was", "were", "has", "have", "had", "be", "in", "on", "at", "from", "until", "by", "for", "to", "and", "or"}
#: Before a bare "one", the words that make it a pronoun ("the first one",
#: "each one"), not a count; "one of them" is one too (`_pronoun_one`).
_ONE_PRONOUN = {
    "the", "this", "that", "each", "every", "which", "any", "first", "next", "last", "other", "another", "same",
    "latest", "earliest", "newest", "oldest", "soonest",
}
#: A determiner before up to two modifiers makes "one" a pronoun: "the urgent
#: one", "the dentist one", "your rent one", "no one" (`_pronoun_one`).
_DETERMINERS = {
    "the", "this", "that", "these", "those", "each", "every", "which", "any", "another", "either", "neither", "no",
    "my", "your", "his", "her", "its", "our", "their", "whose",
}
#: Amounts said as words: "a couple of reminders" is 2 reminders, "two
#: dozen" is 24, "not a single note" is none (`_amounts`).
_AMOUNTS = {"single": 1, "couple": 2, "pair": 2, "dozen": 12}
#: After "nothing" or "none", the word that makes it no count: "nothing
#: else", "none other" say nothing more, not that there are none.
_NOT_A_COUNT = {"else", "more", "other", "further", "besides"}
#: Result keys that are positions, not counts.
_NOT_COUNTS = {"offset", "limit", "page", "id", "seed"}

_TOKEN = re.compile(r"[#/]?\d+(?:[.,:/-]\d+)*(?:st|nd|rd|th|am|pm|%)?|[a-z]+(?:['-][a-z]+)*|[^\sa-z0-9]")
#: "10-12": two figures, where "2026-10-28" (two hyphens) and "9-10am" are
#: dates and times.
_RANGE = re.compile(r"(\d+(?:[.,]\d+)?)-(\d+(?:[.,]\d+)?)$")
_NUMBER_WORD = re.compile(r"(" + "|".join(_TENS) + r")(?:-(" + "|".join(k for k in _UNITS if 0 < _UNITS[k] < 10) + r"))?$")


def _value(token: str) -> str | None:
    """A figure token's value as text ("3", "84", "2.5", "0"), or None when
    the token is not a figure or is a time, a date or an id by its own shape."""
    if token[0].isdigit():
        if re.search(r"[:/-]|(?:st|nd|rd|th|am|pm)$", token):
            return None
        plain = token.rstrip("%").replace(",", "")
        return plain.rstrip("0").rstrip(".") if "." in plain else (plain.lstrip("0") or "0")
    if token in _UNITS:
        return str(_UNITS[token])
    if token in _NONE_WORDS:
        return "0"
    spoken = _NUMBER_WORD.match(token)
    if spoken:
        return str(_TENS[spoken.group(1)] + (_UNITS[spoken.group(2)] if spoken.group(2) else 0))
    return None


def _noun_after(tokens: list[str], i: int) -> str | None:
    """The counted noun a figure at `i` is of, within two words, if any."""
    for word in tokens[i + 1 : i + 4]:
        if word in _NOUNS:
            return _NOUNS[word]
        if word in _STOPS or not word[0].isalpha() or _value(word) is not None:
            return None
    return None


def _dated(tokens: list[str], i: int) -> bool:
    """Whether the figure at `i` is a date, a time or a place by its
    neighbours ("at 9", "2 Nov", "Mon 2", "9 o'clock")."""
    before = tokens[i - 1] if i else ""
    after = tokens[i + 1] if i + 1 < len(tokens) else ""
    return before in _BEFORE_TIME or before in _MONTHS or before in _WEEKDAYS or after in _MONTHS or after in _CLOCK


def _pronoun_one(tokens: list[str], i: int) -> bool:
    """Whether a bare "one" points at a thing rather than counting them:
    "one of them is due", "the first one", "the urgent one is call mum", "no
    one is overdue". The class is a determiner, then up to two plain words
    (an adjective or a noun used as one), then "one". "Only one is waiting"
    and "and one is overdue" count: "only" is no determiner and a stop word
    or a figure ends the reach back."""
    if tokens[i] != "one":
        return False
    after = tokens[i + 1] if i + 1 < len(tokens) else ""
    if after == "of" or (i > 0 and tokens[i - 1] in _ONE_PRONOUN):
        return True
    for word in reversed(tokens[max(0, i - 3) : i]):
        if word in _DETERMINERS:
            return True
        if word == "only" or word in _STOPS or not word[0].isalpha() or _value(word) is not None:
            return False
    return False


def _spoken(tokens: list[str], i: int) -> tuple[int, int] | None:
    """(the number, the index after it) of a number said in several words
    from `i`: "one hundred and five", "a hundred and twenty-one", "two
    thousand three hundred", "twenty one". None for one plain word."""
    total = current = 0
    last, j = "", i
    while j < len(tokens):
        word = tokens[j]
        small = (word in _UNITS and _UNITS[word] > 0) or bool(_NUMBER_WORD.match(word))
        ahead = tokens[j + 1] if j + 1 < len(tokens) else ""
        if word in ("a", "an") and j == i and ahead in ("hundred", "thousand"):
            last = "a"
        elif small and last in ("", "hundred", "thousand", "and"):
            current += int(_value(word) or 0)
            last = "tens" if word in _TENS else "small"
        elif small and last == "tens" and word in _UNITS and _UNITS[word] < 10:
            current += _UNITS[word]
            last = "small"
        elif word in ("hundred", "thousand") and last in ("", "a", "small", "tens"):
            if word == "hundred":
                current = (current or 1) * 100
            else:
                total, current = total + (current or 1) * 1000, 0
            last = word
        elif word == "and" and last in ("hundred", "thousand") and ahead and (ahead in _UNITS or _NUMBER_WORD.match(ahead)):
            last = "and"
        else:
            break
        j += 1
    if last == "and":
        j -= 1
    if j == i or (j - i < 2 and tokens[i] not in ("hundred", "thousand")):
        return None
    return total + current, j


def _amounts(tokens: list[str]) -> list[str]:
    """The tokens with each amount said in words made one figure: "one
    hundred and five" is 105; "a" or a figure before "couple", "dozen" or
    "single" is taken in, and the "of" after it ("a couple of notes" reads
    as "2 notes"); "not a single one" is 0; "nothing else" is no figure; an
    intensifier ("every single note") is none."""
    out: list[str] = []
    taken = False
    i = 0
    while i < len(tokens):
        token = tokens[i]
        ahead = tokens[i + 1] if i + 1 < len(tokens) else ""
        spoken = _spoken(tokens, i)
        if spoken:
            out.append(str(spoken[0]))
            i, taken = spoken[1], False
            continue
        i += 1
        if taken and token == "of":
            taken = False
            continue
        if token in _NONE_WORDS and ahead in _NOT_A_COUNT:
            i += 1
            continue
        taken = token in _AMOUNTS
        if not taken:
            out.append(token)
            continue
        before = out[-1] if out else ""
        if token == "single":
            taken = False
            if before not in ("a", "an"):
                continue
            out[-1] = "1"
            if len(out) > 1 and out[-2] == "not":
                out[-2:] = ["0"]
            if ahead == "one":
                i += 1
            continue
        times = 1 if before in ("a", "an") else _value(before) if token == "dozen" else None
        if times is None:
            out.append(str(_AMOUNTS[token]))
            continue
        out[-1] = str(int(float(times) * _AMOUNTS[token]))
    return out


def _clock_or_year(tokens: list[str], i: int, part: str, known: set[str] | None) -> bool:
    """Whether a figure that counts nothing is a time ("by 10") or a year.
    With `known` (the hours and years of the facts and the question, and
    this year's) it must be one of them, or a time with minutes ("9.30"), or
    follow a month ("October 28, 2026"); without, it is taken as said."""
    if _YEAR.match(part):
        before = tokens[i - 1] if i else ""
        month_day = i > 2 and before == "," and tokens[i - 3] in _MONTHS
        return known is None or before in _MONTHS or month_day or part in known
    if i > 0 and tokens[i - 1] in _BEFORE_CLOCK:
        return known is None or bool(re.match(r"\d{1,2}\.\d\d$", part)) or part in known
    return False


def _known(facts: str, question: str, now: datetime | None) -> set[str]:
    """The hours and the years the facts and the question state, as the text
    of a figure: "at 10am" is 10, "2026-10-28" has 2026."""
    text = f"{facts or ''} {question or ''}".lower()
    known = set(re.findall(r"\b(?:19|20)\d\d\b", text))
    if now:
        known |= {str(now.year + n) for n in (-1, 0, 1)}
    for m in re.finditer(r"\b(\d{1,2})(?::\d\d)?\s*(am|pm)\b|\bat\s+(\d{1,2})\b|\b(\d{1,2}):\d\d\b", text):
        hour = int(m[1] or m[3] or m[4])
        known |= {str(hour), str(hour % 12 or 12), str(hour % 12 + (12 if m[2] == "pm" else 0))}
    return known


def _compound(tokens: list[str], i: int) -> tuple[float, float, int]:
    """The span a run of figure-and-unit pairs says from `i`, as (minutes,
    its smallest unit in minutes, the index after it): "8 weeks and 3 days",
    "2 hours 30 minutes". A pair that is not a smaller unit than the one
    before it ends the run ("3 days 2 weeks" is two spans)."""
    total, last, j = 0.0, float("inf"), i
    while j + 1 < len(tokens):
        value = _value(tokens[j])
        unit = _SPAN_MINUTES.get(tokens[j + 1])
        if value is None or unit is None or unit >= last or _dated(tokens, j):
            break
        total, last, j = total + float(value) * unit, unit, j + 2
        while j < len(tokens) and tokens[j] in ("and", ",", "&"):
            j += 1
    return total, last, j


def _figures(text: str, known: set[str] | None = None) -> list[tuple[str, str | None]]:
    """Every figure the text says that is not a date, a time or an id, as
    (value, the noun it counts, "~<minutes>" for a span, or None for a bare
    figure). A span said in two units is one span, in the smaller
    ("8 weeks and 3 days" is 59 days); a rounded one ("roughly 60 days") ends
    in "h" (`_per`); a range ("10-12") is two figures. "no" is a figure only
    before a counted noun ("no reminders"), never "No, ...". A bare figure
    that reads as a time after "by" or as a year is none when `known`
    (`_clock_or_year`) says it is one."""
    tokens = _amounts(_TOKEN.findall((text or "").lower()))
    out: list[tuple[str, str | None]] = []
    skip = 0
    for i, token in enumerate(tokens):
        if token[0] in "#/" or i < skip:
            continue
        pair = _RANGE.match(token)
        parts = list(pair.groups()) if pair else [token]
        values = ["0" if token == "no" else _value(part) for part in parts]
        if None in values or _dated(tokens, i):
            continue
        after = tokens[i + 1] if i + 1 < len(tokens) else ""
        if after in _SPAN_MINUTES:
            hedged = "h" if any(w in _HEDGES for w in tokens[max(0, i - 2) : i]) else ""
            if pair:
                out.extend((v, f"~{_SPAN_MINUTES[after]:.10g}{hedged}") for v in values)
                continue
            minutes, unit, skip = _compound(tokens, i)
            out.append((f"{minutes / unit:.6g}", f"~{unit:.10g}{hedged}"))
            continue
        noun = _noun_after(tokens, i)
        for part, value in zip(parts, values):
            if noun is None and (token == "no" or _pronoun_one(tokens, i) or _clock_or_year(tokens, i, part, known)):
                continue
            out.append((value, noun))
    return out


def said_counts(text: str) -> dict[str, set[str]]:
    """The counted statements of the engine's own sentence ("You have 3
    reminders waiting" is {"reminder": {"3"}})."""
    out: dict[str, set[str]] = {}
    for value, noun in _figures(text):
        if noun and noun != "*" and not _is_span(noun):
            out.setdefault(noun, set()).add(value)
    return out


def _noun_of_key(key: str) -> str | None:
    for part in re.split(r"[_\s]+", key.lower()):
        if part in _NOUNS and _NOUNS[part] != "*":
            return _NOUNS[part]
    return None


def result_counts(tool: str, result: object) -> dict[str, set[str]]:
    """The totals a read tool's result holds, by what they count: an int or a
    list's length under a key that names a noun ("total_notes", "tags"), or
    under a plain total the tool's own noun; a row's "notes" or "count", and
    each figure of a breakdown ("by_category"), is a count of notes. Any
    other nested dict ("filters": {"limit": 10}) holds no counts."""
    out: dict[str, set[str]] = {}
    if not isinstance(result, dict):
        return out
    own = TOOL_NOUNS.get(tool)

    def add(noun: str | None, n: object) -> None:
        if noun and isinstance(n, int) and not isinstance(n, bool):
            out.setdefault(noun, set()).add(str(n))

    for key, value in result.items():
        if key in _NOT_COUNTS or key.endswith("_id"):
            continue
        noun = _noun_of_key(key) or own
        if isinstance(value, list):
            add(noun, len(value))
            for row in value:
                if isinstance(row, dict):
                    add("note", row.get("notes"))
                    add("note", row.get("count"))
        elif isinstance(value, dict) and key.startswith("by_"):
            for n in value.values():
                add("note", n)
        else:
            add(noun, value)
    return out


#: A statistic's rows count notes, except where a kind says otherwise.
_ROW_NOUNS = {"linked": "link"}


def rows_counts(stats: dict) -> dict[str, set[str]]:
    """A statistic's rows as counts: a row named for a noun ("tags",
    "documents", "mind maps") counts that; a row named for a tag, a
    category or a note counts notes (or links, for the most linked)."""
    out: dict[str, set[str]] = {}
    for row in stats.get("facts") or []:
        if not isinstance(row, dict) or not isinstance(row.get("count"), int):
            continue
        label = str(row.get("label") or "").lower().split()
        noun = _NOUNS.get(label[-1]) if label else None
        noun = noun if noun and noun != "*" else _ROW_NOUNS.get(str(stats.get("kind") or ""), "note")
        out.setdefault(noun, set()).add(str(row["count"]))
    return out


def merged(*parts: dict[str, set[str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for part in parts:
        for noun, values in (part or {}).items():
            out.setdefault(noun, set()).update(values)
    return out


def _is_span(noun: str | None) -> bool:
    return bool(noun) and noun.startswith("~")


def _per(noun: str) -> float:
    """A span's unit in minutes, from its tag ("~1440", "~1440h")."""
    return float(noun[1:].rstrip("h"))


def _spans(text: str) -> list[float]:
    """The spans a text states, in minutes."""
    return [float(v) * _per(n) for v, n in _figures(text) if _is_span(n)]


def _span_kept(value: str, noun: str, spans: list[float]) -> bool:
    """Whether a span the prose says is one of `spans`: the same length, or
    the length rounded to the nearest of the unit the prose uses ("8 weeks"
    for 59 days, "2 months" for 59 days, never "1 month" or "1 year"), or,
    when the prose says it is rounded ("roughly 60 days"), within 5%."""
    said, unit = float(value), _per(noun)
    for span in spans:
        if abs(said * unit - span) < 1e-6 or abs(said - span / unit) <= 0.5 + 1e-9:
            return True
        if noun.endswith("h") and span and abs(said * unit - span) / span <= 0.05:
            return True
    return False


_MONTH_NUMBER = {name: n + 1 for n, name in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
_MONTH_WORD = "|".join(sorted(_MONTHS, key=len, reverse=True))
_AT_TIME = r"(?:,?\s+(?:at\s+)?(\d{1,2})(?::(\d\d))?\s*(am|pm)?\b)?"
#: "Monday 12 October at 9am", "28 Oct", "Oct 28, 2026", "2026-10-28 09:00".
_DAY_FIRST = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_WORD})\b(?:,?\s+(\d{{4}}))?{_AT_TIME}")
_MONTH_FIRST = re.compile(rf"\b({_MONTH_WORD})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?")
_ISO = re.compile(r"\b(\d{4})-(\d\d)-(\d\d)(?:[t ](\d\d):(\d\d))?")


def _moments(text: str, now: datetime) -> list[tuple[datetime, bool]]:
    """The dates a text carries, as (when, whether it names a time of day).
    A date with no year is the year that puts it nearest to `now`."""
    found: list[tuple[datetime, bool]] = []

    def add(year: int | None, month: int, day: int, hour: int | None = None, minute: int = 0) -> None:
        years = (year,) if year else (now.year - 1, now.year, now.year + 1)
        tries = [datetime(y, month, day, hour or 0, minute) for y in years if _valid(y, month, day)]
        if tries:
            found.append((min(tries, key=lambda m: abs(m - now)), hour is not None))

    lowered = (text or "").lower()
    for m in _ISO.finditer(lowered):
        add(int(m[1]), int(m[2]), int(m[3]), int(m[4]) if m[4] else None, int(m[5] or 0))
    for m in _DAY_FIRST.finditer(lowered):
        hour = int(m[4]) if m[4] and (m[5] or m[6]) else None
        if hour is not None and m[6]:
            hour = hour % 12 + (12 if m[6] == "pm" else 0)
        add(int(m[3]) if m[3] else None, _MONTH_NUMBER[m[2][:3]], int(m[1]), hour, int(m[5] or 0))
    for m in _MONTH_FIRST.finditer(lowered):
        add(int(m[3]) if m[3] else None, _MONTH_NUMBER[m[1][:3]], int(m[2]))
    return found


def _valid(year: int, month: int, day: int) -> bool:
    try:
        datetime(year, month, day)
    except ValueError:
        return False
    return True


def _dated_spans(facts: str, now: datetime | None) -> list[float]:
    """The spans the dates in the facts make, in minutes: each date from
    `now`, each from each, by the clock where it names a time and by the
    calendar day where it does not ("in 2 days" for a date two days off)."""
    if now is None:
        return []
    # The facts' dates are wall-clock dates with no zone; `user_now` is
    # aware, so compare on the user's wall clock.
    now = now.replace(tzinfo=None)
    moments = _moments(facts, now)
    out: list[float] = []
    points = [(now, True)] + moments
    for a in range(len(points)):
        for b in range(a + 1, len(points)):
            first, second = points[a][0], points[b][0]
            out.append(abs((second - first).total_seconds()) / 60)
            out.append(abs((second.date() - first.date()).days) * 1440.0)
    return out


def _kept(value: str, noun: str | None, counts: dict[str, set[str]], every: set[str], stated: set[str], spans: list[float]) -> bool:
    """One figure of the prose against the engine's counts and spans (`keeps`)."""
    if _is_span(noun):
        return _span_kept(value, noun, spans)
    if noun is None:
        return value in every or value in stated
    if counts:
        return value in (every if noun == "*" else counts.get(noun, set()))
    return value in stated


def keeps(prose: str, facts: str, question: str, counts: dict[str, set[str]], needs_figure: bool, now: datetime | None = None) -> bool:
    """Whether the prose keeps to the engine's facts.

    With counts: every count the prose says matches the engine's count of
    that noun (a noun the engine did not count is refused), and a bare
    figure is one of the counts, or a figure the facts or the question state
    outside a date or a time; "one of them" and "the first one" are no figure.
    With none (a worked sum, a conversion): every figure is one the facts or
    the question state. Either way, an answer with no list under it says the
    figure it was asked for."""
    if not prose.strip():
        return False
    said = _figures(prose, _known(facts, question, now))
    stated = {v for v, _n in _figures(facts)} | {v for v, _n in _figures(question)}
    every = set().union(*counts.values()) if counts else set()
    spans = _spans(facts) + _spans(question) + _dated_spans(facts, now)
    if not all(_kept(value, noun, counts, every, stated, spans) for value, noun in said):
        return False
    return not needs_figure or _says_asked(said, facts, question, every)


def _says_asked(said: list[tuple[str, str | None]], facts: str, question: str, every: set[str]) -> bool:
    """Whether the prose says the figure it was asked for: one of the counts,
    or a figure or a span the facts state and the question does not ("2
    hours is 120 minutes" asks for the 120, in any unit but the question's)."""
    asked = _figures(question)
    stated = [(v, n) for v, n in _figures(facts) if (v, n) not in asked]
    asked_for = every or {v for v, n in stated if not _is_span(n)} - {v for v, _n in asked}
    asked_spans = [float(v) * _per(n) for v, n in stated if _is_span(n)]
    if not asked_for and not asked_spans:
        return True
    return any(
        value in asked_for or (_is_span(noun) and (value, noun) not in asked and _span_kept(value, noun, asked_spans))
        for value, noun in said
    )
