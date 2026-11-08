"""Text transforms on text the person pastes (CHAT_PLAN T6): "uppercase: hello
there", "sort these lines: ...", "slugify My Trip To Lisbon".

The transform reads the question only. No note is read, quoted or changed:
the result is a draft in a code block, and the reply says nothing was saved.
A transform that needs its words set apart (sort, reverse, remove duplicates,
number) answers only when they follow a colon, a quote or a new line, so
"sort my notes by date" is never taken for one.

The head of the message (the part before the pasted text) is short and read
with blanks collapsed to single spaces; the pasted text is never matched by a
pattern, only split and mapped, so a long paste costs a single pass.
"""

from __future__ import annotations

import re
import unicodedata

from tessellate.ai.composer_study import Ctx, Reply

#: Longest paste read; more is a document, not a snippet.
MAX_TEXT = 20000
_HEAD_LIMIT = 100

_OPS = {
    "uppercase": "upper", "upper case": "upper", "all caps": "upper",
    "lowercase": "lower", "lower case": "lower",
    "title case": "title",
    "slugify": "slug",
    "reverse": "reverse",
    "sort": "sort",
    "remove duplicate lines": "dedupe", "remove duplicates": "dedupe", "dedupe": "dedupe", "deduplicate": "dedupe",
    "number the lines": "number", "number lines": "number",
}
for _det in ("", "these ", "the ", "those ", "my ", "this "):
    for _noun in ("lines", "items", "words"):
        _OPS[f"join {_det}{_noun} with commas"] = "join"
        _OPS[f"join {_det}{_noun} with a comma"] = "join"
        _OPS[f"put {_det}{_noun} on one line"] = "join"
        _OPS[f"split {_det}{_noun} on commas"] = "split"
        _OPS[f"split {_det}{_noun} by commas"] = "split"
        _OPS[f"split {_det}{_noun} at commas"] = "split"
        _OPS[f"split {_det}{_noun} into lines"] = "split"
for _det in ("", "these ", "the ", "this ", "that "):
    _OPS[f"split {_det}into lines"] = "split"
    _OPS[f"count {_det}characters"] = "count"
_OPS.update({"join with commas": "join", "join with a comma": "join", "comma separate": "join", "split on commas": "split", "split by commas": "split",
             "split into lines": "split", "character count": "count", "char count": "count", "count characters": "count", "count chars": "count"})
_NEEDS_DELIMITER = frozenset({"reverse", "sort", "dedupe", "number", "join", "split", "count"})
_NAMES = "|".join(sorted((re.escape(k) for k in _OPS), key=len, reverse=True))
_HEAD = re.compile(
    rf"^(?:please )?(?:(?:make|turn|change|convert|put) (?:this|that|it|the text|these lines|the lines|my text) (?:in|into|to)? ?)?(?P<op>{_NAMES})(?: (?P<rest>\S.*))?$", re.I
)
_FILLER = re.compile(r"^(?:(?:this|that|the|these|those) (?:text|lines|words|list|items|sentence|string) )", re.I)
_FILLER_ONLY = re.compile(r"^(?:(?:this|that|the|these|those|my) )*(?:text|lines|words|list|items|sentence|string|this|that|the|these|those)$", re.I)
#: Words that name the notebook's own things: "uppercase my notes about X" is a question about notes, not text to
#: transform, unless the words are set apart by a colon or quotes.
_NOTEBOOK = re.compile(r"\b(?:notes?|reminders?|tasks?|todos?|entry|entries|plans?|lists?|journal|diary)\b", re.I)
_SMALL = frozenset("a an the and but or for nor on at to by of in up as".split())
_LEADS = {
    "upper": ("In capitals:", "the text in capitals"),
    "lower": ("In lower case:", "the text in lower case"),
    "title": ("In title case:", "the text in title case"),
    "slug": ("As a slug:", "the text as a lower-case slug joined by hyphens"),
    "reverse": ("Reversed:", "the text with its letters in reverse order"),
    "sort": ("Sorted:", "the lines or comma-separated items sorted A to Z"),
    "dedupe": ("Without duplicates:", "the lines or comma-separated items with repeats removed, first kept"),
    "number": ("Numbered:", "each line numbered from 1"),
    "join": ("Joined with commas:", "the lines joined into one line with commas"),
    "split": ("Split into lines:", "the comma-separated items, one to a line"),
}


def _title_case(text: str) -> str:
    words = text.split(" ")
    last = len(words) - 1
    out = []
    for i, w in enumerate(words):
        low = w.lower()
        out.append(low if (0 < i < last and low in _SMALL) else low[:1].upper() + low[1:])
    return " ".join(out)


def _slug(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def _items(text: str) -> tuple[list[str], str]:
    """The lines of a paste, else its comma-separated items, and the joiner."""
    if "\n" in text.strip():
        return [ln.strip() for ln in text.strip().splitlines() if ln.strip()], "\n"
    return [p.strip() for p in text.split(",") if p.strip()], ", "


def _dedupe(text: str) -> str:
    items, glue = _items(text)
    seen: dict[str, str] = {}
    for it in items:
        seen.setdefault(it.casefold(), it)
    return glue.join(seen.values())


def _join(text: str) -> str:
    return ", ".join(ln.strip() for ln in text.strip().splitlines() if ln.strip()) if "\n" in text.strip() else ""


def _split(text: str) -> str:
    return "\n".join(p.strip() for p in text.split(",") if p.strip()) if "," in text else ""


def _sort(text: str) -> str:
    items, glue = _items(text)
    return glue.join(sorted(items, key=str.casefold))


def _number(text: str) -> str:
    return "\n".join(f"{n}. {it}" for n, it in enumerate(_items(text)[0], 1))


_APPLY = {
    "upper": str.upper, "lower": str.lower, "title": lambda t: _title_case(" ".join(t.split())), "slug": _slug, "reverse": lambda t: t[::-1],
    "dedupe": _dedupe, "join": _join, "split": _split, "sort": _sort, "number": _number,
}


def _apply(op: str, text: str) -> str:
    return _APPLY[op](text)


def _unquote(text: str) -> str:
    text = text.strip()
    pairs = (('"', '"'), ("“", "”"), ("'", "'"))
    for a, b in pairs:
        if len(text) >= 2 and text[0] == a and text[-1] == b:
            return text[1:-1].strip()
    return text


def _head(raw: str) -> tuple[str, str, int] | None:
    """(operation, words after it, index of the colon or new line or -1)."""
    cut = next((i for i, ch in enumerate(raw[:_HEAD_LIMIT]) if ch in ":\n"), -1)
    if cut < 0 and len(raw) > _HEAD_LIMIT:
        return None
    found = _HEAD.match(" ".join((raw[:cut] if cut >= 0 else raw).split()))
    if not found:
        return None
    return _OPS[found["op"].lower()], found["rest"] or "", cut


def _body(op: str, rest: str, cut: int, raw: str) -> str | None:
    """The pasted text: after the delimiter, else (for the plain transforms)
    the words after the instruction."""
    if cut >= 0:
        return None if rest and not _FILLER_ONLY.match(rest) else _unquote(raw[cut + 1:])
    if op in _NEEDS_DELIMITER:
        quoted = _unquote(rest)
        return quoted if quoted != rest.strip() else None
    lead = _FILLER.match(rest)
    body = _unquote(rest[lead.end():] if lead else rest)
    quoted = body != rest.strip()
    return None if not quoted and _NOTEBOOK.search(body) else body


def _read(raw: str) -> tuple[str, str] | None:
    """(operation, pasted text) or None."""
    raw = raw.strip()
    if not raw or len(raw) > MAX_TEXT + _HEAD_LIMIT:
        return None
    head = _head(raw)
    if head is None:
        return None
    op, rest, cut = head
    body = _body(op, rest, cut, raw)
    return (op, body) if body and len(body) <= MAX_TEXT else None


def _count(body: str) -> Reply:
    chars = len(body)
    bare = sum(1 for ch in body if not ch.isspace())
    return Reply(f"{chars} character{'s' if chars != 1 else ''}, {bare} without spaces.\n\n_Read as the characters in the text you gave, blanks and new lines counted in the first number. No note was read._")


def answer(ctx: Ctx) -> Reply | None:
    got = _read(ctx.question or "")
    if got is None:
        return None
    op, body = got
    if op == "count":
        return _count(body)
    lead, read = _LEADS[op]
    result = _apply(op, body)
    if not result:
        return None
    return Reply(f"{lead}\n\n```\n{result}\n```\n\n_Read as {read}. A draft only: nothing was saved or changed._")
