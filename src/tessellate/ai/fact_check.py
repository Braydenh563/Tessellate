"""Whether a model's words keep to the app's counts (CHAT_PLAN decision 75:
with a model up the model writes the answer from the engine's facts, and its
prose may not contradict them).

A count is a figure attached to a counted noun ("3 reminders", "no notes",
"one tag"), compared with the counts the engine itself produced: the totals
and row counts of the tool result or the statistic (`result_counts`,
`rows_counts`) and the counted statements of the engine's own lead sentence
(`said_counts`). A date ("Mon 2 Nov"), a time ("14:02", "at 9"), an id
("#/notes/12") and a span ("in 3 days") are never counts, so a digit there
can neither excuse a miscount nor be one. "one", "no", "none", "nothing" and
"zero" are figures like any other.
"""

from __future__ import annotations

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
#: After a figure, the word that makes it a span or a time, not a count.
_SPANS = {
    "second", "seconds", "minute", "minutes", "min", "mins", "hour", "hours", "hr", "hrs", "day", "days", "week",
    "weeks", "month", "months", "year", "years", "am", "pm", "o'clock", "oclock",
}
#: Before a figure, the word that makes it a time or a place ("at 9", "#12").
_BEFORE_TIME = {"at", "#", "/", "no.", "number"}
#: Words that end the reach from a figure to its noun ("one of the notes"
#: does not say there is one note).
_STOPS = {"of", "is", "are", "was", "were", "has", "have", "had", "be", "in", "on", "at", "from", "until", "by", "for", "to", "and", "or"}
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


def _figures(text: str) -> list[tuple[str, str | None]]:
    """Every figure the text says that is not a date, a time, an id or a
    span, as (value, the noun it counts or None for a bare figure). "no" is
    a figure only before a counted noun ("no reminders"), never "No, ..."."""
    tokens = _TOKEN.findall((text or "").lower())
    out: list[tuple[str, str | None]] = []
    for i, token in enumerate(tokens):
        if token[0] in "#/":
            continue
        value = "0" if token == "no" else _value(token)
        if value is None:
            continue
        before = tokens[i - 1] if i else ""
        after = tokens[i + 1] if i + 1 < len(tokens) else ""
        if before in _BEFORE_TIME or before in _MONTHS or before in _WEEKDAYS or after in _MONTHS or after in _SPANS:
            continue
        noun = _noun_after(tokens, i)
        if token == "no" and noun is None:
            continue
        out.append((value, noun))
    return out


def said_counts(text: str) -> dict[str, set[str]]:
    """The counted statements of the engine's own sentence ("You have 3
    reminders waiting" is {"reminder": {"3"}})."""
    out: dict[str, set[str]] = {}
    for value, noun in _figures(text):
        if noun and noun != "*":
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


def _kept(value: str, noun: str | None, counts: dict[str, set[str]], every: set[str], stated: set[str]) -> bool:
    """One figure of the prose against the engine's counts (`keeps`)."""
    if noun is None:
        return value == "1" or value in every or value in stated
    if counts:
        return value in (every if noun == "*" else counts.get(noun, set()))
    return value in stated


def keeps(prose: str, facts: str, question: str, counts: dict[str, set[str]], needs_figure: bool) -> bool:
    """Whether the prose keeps to the engine's facts.

    With counts: every count the prose says matches the engine's count of
    that noun (a noun the engine did not count is refused), and a bare
    figure is one of the counts, or a figure the facts or the question state
    outside a date or a time; a bare "one" ("one of them is due") stands.
    With none (a worked sum, a conversion): every figure is one the facts or
    the question state. Either way, an answer with no list under it says the
    figure it was asked for."""
    if not prose.strip():
        return False
    said = _figures(prose)
    stated = {v for v, _n in _figures(facts)} | {v for v, _n in _figures(question)}
    every = set().union(*counts.values()) if counts else set()
    if not all(_kept(value, noun, counts, every, stated) for value, noun in said):
        return False
    if not needs_figure:
        return True
    asked_for = every or ({v for v, _n in _figures(facts)} - {v for v, _n in _figures(question)})
    return not asked_for or any(value in asked_for for value, _n in said)
