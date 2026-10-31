"""**The sentence a request that did not validate is answered with** (audit
1031 BK8).

FastAPI's validator names a field by its Python name and describes the fault
in pydantic's words ("String should have at most 200 characters"), so a bad
reminder time said "Check the due at and try again." and a too-long name
quoted the library. This turns one error into a sentence a person can act on:
the field by its label (`LABELS`, a name the screen uses where it differs
from the code's) and the limit in the message when the fault is a limit.

Every case not listed falls back to "Check the <label> and try again.", the
sentence the app used for all of them before, so a new validator is never
silent.
"""

from __future__ import annotations

#: Field name (the last part of the location) to the words the screen uses.
#: Only names that differ from the code's own spelling go here.
LABELS: dict[str, str] = {
    "due_at": "due time",
    "remind_at": "reminder time",
    "starts_at": "start time",
    "ends_at": "end time",
    "entry_id": "note id",
    "content": "text",
    "category": "name",
    "q": "search",
}


def label(field: str) -> str:
    """The words for the last part of a field location."""
    last = field.rsplit(".", 1)[-1]
    return LABELS.get(last) or last.replace("_", " ")


def _count(n: object) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def _bound(kind: str, ctx: dict) -> str | None:
    """A numeric bound as "must be 0 or more"; `kind` is pydantic's type."""
    edge = {
        "greater_than_equal": ("ge", "{} or more"),
        "less_than_equal": ("le", "{} or less"),
        "greater_than": ("gt", "more than {}"),
        "less_than": ("lt", "less than {}"),
    }.get(kind)
    if edge is None or edge[0] not in ctx:
        return None
    return "must be " + edge[1].format(_count(ctx[edge[0]]))


def _length(kind: str, name: str, ctx: dict) -> str | None:
    """The four length errors, for a string or a list; None for any other kind."""
    if kind == "string_too_short" and ctx.get("min_length", 2) <= 1 and "min_length" in ctx:
        return f"The {name} can't be empty."
    rules = {
        "string_too_long": ("max_length", "The {name} can be at most {n} characters."),
        "string_too_short": ("min_length", "The {name} needs at least {n} characters."),
        "too_long": ("max_length", "The {name} can hold at most {n} items."),
        "too_short": ("min_length", "The {name} needs at least {n} items."),
    }
    rule = rules.get(kind)
    if rule is None or rule[0] not in ctx:
        return None
    return rule[1].format(name=name, n=_count(ctx[rule[0]]))


#: Error types with a fixed sentence, `{name}` filled in.
_PLAIN = {
    "missing": "The {name} is missing.",
    "int_parsing": "The {name} must be a whole number.",
    "int_from_float": "The {name} must be a whole number.",
    "int_type": "The {name} must be a whole number.",
}


def sentence(kind: str, field: str, ctx: dict | None = None) -> str:
    """One validation error as a sentence; `kind` is pydantic's error type."""
    ctx = ctx or {}
    name = label(field)
    text = _length(kind, name, ctx)
    if text:
        return text
    if kind in _PLAIN:
        return _PLAIN[kind].format(name=name)
    if kind.startswith(("datetime_", "date_", "time_")) and "parsing" in kind:
        return f"The {name} isn't a date or time that can be read."
    bound = _bound(kind, ctx)
    if bound:
        return f"{name[:1].upper() + name[1:]} {bound}."
    return f"Check the {name} and try again."


def describe(errors: list[dict]) -> tuple[str, list[dict]]:
    """The one `detail` sentence and the `fields` list for a list of pydantic
    errors. The input a caller sent is never read, so it is never echoed."""
    fields = []
    for error in errors:
        loc = [str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")]
        field = ".".join(loc)
        text = sentence(str(error.get("type", "")), field, error.get("ctx") or {}) if field else (
            "That was not accepted. Check what you entered and try again."
        )
        fields.append({"field": field, "message": text})
    if not fields:
        return "That was not accepted. Check what you entered and try again.", fields
    return fields[0]["message"], fields
