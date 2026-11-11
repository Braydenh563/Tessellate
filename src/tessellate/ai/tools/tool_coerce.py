"""Reading a model's arguments as the schema types them (INBOX 527).

Moved from `tool_run.py` (module line cap): the per-type coercers, `_coerce`
and `_describe_param`. Imports run one way: this file imports nothing of the tools.
"""

from __future__ import annotations

import json
import math
import re

#: Words read as a boolean (INBOX 527). Before `check_arguments`, `pin_note`
#: read the string "false" as true.
_TRUE_WORDS = frozenset({"true", "yes", "y", "on", "1"})
_FALSE_WORDS = frozenset({"false", "no", "n", "off", "0", "none", ""})
_INT_TEXT = re.compile(r"#?-?\d{1,12}")


def _coerce_array(value: object, schema: dict) -> tuple[object, bool]:
    items = schema.get("items") or {}
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                value = json.loads(text)
            except (ValueError, RecursionError):  # a runaway "[[[[" is a bad argument
                return value, False
        elif items.get("type") == "string":
            value = [part.strip() for part in text.split(",") if part.strip()]
        else:
            value = [value]
    if not isinstance(value, list):
        value = [value]
    if not items.get("type"):
        return value, True
    out = []
    for item in value:
        coerced, ok = _coerce(item, items)
        if not ok:
            return value, False
        out.append(coerced)
    return out, True


def _coerce_integer(value: object, schema: dict) -> tuple[object, bool]:
    if isinstance(value, bool):
        return value, False
    if isinstance(value, int):
        return value, True
    if isinstance(value, float) and value.is_integer():
        return int(value), True
    if isinstance(value, str) and _INT_TEXT.fullmatch(value.strip()):
        return int(value.strip().lstrip("#")), True
    return value, False


def _coerce_number(value: object, schema: dict) -> tuple[object, bool]:
    if isinstance(value, bool):
        return value, False
    # Finite only: "nan" and "inf" parse as floats, and a handler that
    # compares or divides by one misbehaves without saying so (sweep 1004).
    if isinstance(value, int):
        return value, True
    if isinstance(value, float):
        return (value, True) if math.isfinite(value) else (value, False)
    try:
        number = float(str(value).strip())
    except ValueError:
        return value, False
    return (number, True) if math.isfinite(number) else (value, False)


def _coerce_boolean(value: object, schema: dict) -> tuple[object, bool]:
    if isinstance(value, bool):
        return value, True
    word = str(value).strip().lower()
    if word in _TRUE_WORDS or word in _FALSE_WORDS:
        return word in _TRUE_WORDS, True
    return value, False


def _coerce_string(value: object, schema: dict) -> tuple[object, bool]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        return value, False
    enum = schema.get("enum")
    if enum and value not in enum:
        folded = {str(e).lower(): e for e in enum}
        hit = folded.get(value.strip().lower())
        return (hit, True) if hit is not None else (value, False)
    return value, True


def _coerce_object(value: object, schema: dict) -> tuple[object, bool]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):  # a runaway nesting is a bad argument
            return value, False
    return value, isinstance(value, dict)


#: How a value is read as each schema type; a type not here passes as it is.
_COERCERS = {
    "integer": _coerce_integer,
    "number": _coerce_number,
    "boolean": _coerce_boolean,
    "string": _coerce_string,
    "array": _coerce_array,
    "object": _coerce_object,
}


def _coerce(value: object, schema: dict) -> tuple[object, bool]:
    """(value as the schema's type, True), or (value, False) when it cannot be
    read as that type without guessing."""
    kind = schema.get("type")
    coercer = _COERCERS.get(kind) if isinstance(kind, str) else None
    return (value, True) if coercer is None else coercer(value, schema)


def _describe_param(key: str, schema: dict) -> str:
    """`note_id (integer)`, `tags (list of strings)`, `priority ('low' or ...)`."""
    kind = schema.get("type", "value")
    if kind == "array":
        kind = f"list of {(schema.get('items') or {}).get('type', 'value')}s"
    if schema.get("enum"):
        kind = " or ".join(repr(e) for e in schema["enum"])
    return f"{key} ({kind})"
