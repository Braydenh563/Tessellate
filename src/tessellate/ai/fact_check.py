"""Whether a model's words keep to the app's counts (CHAT_PLAN decision 75:
with a model up the model writes the answer from the engine's facts, and its
prose may not contradict them).

A count is a figure attached to a counted noun ("3 reminders", "no notes",
"one tag"), compared with the counts the engine itself produced: the totals
and row counts of the tool result or the statistic (`result_counts`,
`rows_counts`) and the counted statements of the engine's own lead sentence
(`said_counts`). A date ("Mon 2 Nov"), a time ("14:02", "at 9"), an id
("#/notes/12") are never counts, so a digit there can neither excuse a
miscount nor be one. A span ("120 minutes", "59 days") is checked against
the spans the facts state, in any unit, and stands when they state none.
"one", "no", "none", "nothing" and "zero" are figures like any other.
"""

from __future__ import annotations

import math
import re

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
_MONTHS = {
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
    "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}
_WEEKDAYS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "mon", "tue", "tues", "wed", "thu", "thur", "thurs", "fri", "sat", "sun",
}
#: After a figure, the word that makes it a time of day, never a count.
_CLOCK = {"am", "pm", "o'clock", "oclock"}
#: After a figure, the unit that makes it a span ("3 days", "120 minutes"),
#: in minutes. A span is read as (value, "~<minutes>") and checked only
#: against spans the facts state (`_span_kept`): "in 3 days" under a list
#: of reminders is the model's, "59 days away" is the engine's.
_SPAN_MINUTES = {
    **dict.fromkeys(("second", "seconds", "sec", "secs"), 1 / 60),
    **dict.fromkeys(("minute", "minutes", "min", "mins"), 1),
    **dict.fromkeys(("hour", "hours", "hr", "hrs"), 60),
    **dict.fromkeys(("day", "days"), 1440),
    **dict.fromkeys(("week", "weeks"), 10080),
    **dict.fromkeys(("fortnight", "fortnights"), 20160),
    **dict.fromkeys(("month", "months"), 43830),
    **dict.fromkeys(("year", "years"), 525960),
}
#: Before a figure, the word that makes it a time or a place ("at 9", "#12").
_BEFORE_TIME = {"at", "#", "/", "no.", "number"}
#: Words that end the reach from a figure to its noun ("one of the notes"
#: does not say there is one note).
_STOPS = {"of", "is", "are", "was", "were", "has", "have", "had", "be", "in", "on", "at", "from", "until", "by", "for", "to", "and", "or"}
#: Before a bare "one", the words that make it a pronoun ("the first one",
#: "each one"), not a count; "one of them" is one too (`_pronoun_one`).
_ONE_PRONOUN = {
    "the", "this", "that", "each", "every", "which", "any", "first", "next", "last", "other", "another", "same",
    "latest", "earliest", "newest", "oldest", "soonest",
}
#: Result keys that are positions, not counts.
_NOT_COUNTS = {"offset", "limit", "page", "id", "seed"}

_TOKEN = re.compile(r"[#/]?\d+(?:[.,:/]\d+)*(?:st|nd|rd|th|am|pm|%)?|[a-z]+(?:['-][a-z]+)*|[^\sa-z0-9]")
_NUMBER_WORD = re.compile(r"(" + "|".join(_TENS) + r")(?:-(" + "|".join(k for k in _UNITS if 0 < _UNITS[k] < 10) + r"))?$")


def _value(token: str) -> str | None:
    """A figure token's value as text ("3", "84", "2.5", "0"), or None when
    the token is not a figure or is a time, a date or an id by its own shape."""
    if token[0].isdigit():
        if re.search(r"[:/]|(?:st|nd|rd|th|am|pm)$", token):
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
    "one of them is due", "the first one". "Only one is waiting" counts."""
    if tokens[i] != "one":
        return False
    after = tokens[i + 1] if i + 1 < len(tokens) else ""
    return after == "of" or (i > 0 and tokens[i - 1] in _ONE_PRONOUN)


def _figures(text: str) -> list[tuple[str, str | None]]:
    """Every figure the text says that is not a date, a time or an id, as
    (value, the noun it counts, "~<minutes>" for a span, or None for a bare
    figure). "no" is
    a figure only before a counted noun ("no reminders"), never "No, ..."."""
    tokens = _TOKEN.findall((text or "").lower())
    out: list[tuple[str, str | None]] = []
    for i, token in enumerate(tokens):
        if token[0] in "#/":
            continue
        value = "0" if token == "no" else _value(token)
        if value is None:
            continue
        if _dated(tokens, i):
            continue
        after = tokens[i + 1] if i + 1 < len(tokens) else ""
        noun = f"~{_SPAN_MINUTES[after]}" if after in _SPAN_MINUTES else _noun_after(tokens, i)
        if (token == "no" and noun is None) or (noun is None and _pronoun_one(tokens, i)):
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
    under a plain total the tool's own noun; a row's "notes" or "count" is
    a count of notes."""
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
        elif isinstance(value, dict):
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


def _spans(text: str) -> list[float]:
    """The spans a text states, in minutes."""
    return [float(v) * float(n[1:]) for v, n in _figures(text) if _is_span(n)]


def _span_kept(value: str, unit: float, spans: list[float]) -> bool:
    """Whether a span the prose says is one the facts state, in any unit:
    "59 days" is "8 weeks" or "about 2 months" too, never "90 days"."""
    said = float(value)
    for span in spans:
        whole = span / unit
        if abs(said * unit - span) < 1e-6 or said in (math.floor(whole), round(whole), math.ceil(whole)):
            return True
    return False


def _kept(value: str, noun: str | None, counts: dict[str, set[str]], every: set[str], stated: set[str], spans: list[float]) -> bool:
    """One figure of the prose against the engine's counts and spans (`keeps`)."""
    if _is_span(noun):
        return not spans or _span_kept(value, float(noun[1:]), spans)
    if noun is None:
        return value in every or value in stated
    if counts:
        return value in (every if noun == "*" else counts.get(noun, set()))
    return value in stated


def keeps(prose: str, facts: str, question: str, counts: dict[str, set[str]], needs_figure: bool) -> bool:
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
    said = _figures(prose)
    stated = {v for v, _n in _figures(facts)} | {v for v, _n in _figures(question)}
    every = set().union(*counts.values()) if counts else set()
    if not all(_kept(value, noun, counts, every, stated, _spans(facts)) for value, noun in said):
        return False
    return not needs_figure or _says_asked(said, facts, question, every)


def _says_asked(said: list[tuple[str, str | None]], facts: str, question: str, every: set[str]) -> bool:
    """Whether the prose says the figure it was asked for: one of the counts,
    or a figure or a span the facts state and the question does not ("2
    hours is 120 minutes" asks for the 120, in any unit but the question's)."""
    asked = _figures(question)
    stated = [(v, n) for v, n in _figures(facts) if (v, n) not in asked]
    asked_for = every or {v for v, n in stated if not _is_span(n)} - {v for v, _n in asked}
    asked_spans = [float(v) * float(n[1:]) for v, n in stated if _is_span(n)]
    if not asked_for and not asked_spans:
        return True
    return any(
        value in asked_for or (_is_span(noun) and (value, noun) not in asked and _span_kept(value, float(noun[1:]), asked_spans))
        for value, noun in said
    )
