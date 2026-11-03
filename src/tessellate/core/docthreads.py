"""The sidecar behind a document's comments (audit 1102 DX24, audit 1028 D26).

A comment is still the inline `%%remark%%` in the file: it travels with the
text, with an export (as a footnote) and with a revision. What the file cannot
say is who wrote it, when, what was answered and whether it is settled, so that
lives here, one JSON list in `documents.threads`, never in the text.

Each record is `{id, key, author, at, text, replies, resolved, resolved_at,
target, line, own}`. `key` is the remark's text hash plus its place among
remarks that say the same thing; the browser derives it and matches records to
remarks (`docThreadsReconcile` in documents-comments.js), so a rename of the
words around a remark changes nothing. A resolved record has no remark in the
file any more (resolving removes it, as it always did); `target`, `line` and
`own` are what Reopen needs to put it back.

This module only validates. The server never reads a thread for any decision,
so a hand-edited or hostile list can do no worse than be dropped to what fits
the shape and the caps below.
"""

from __future__ import annotations

import json
from typing import Any

MAX_THREADS = 500
MAX_REPLIES = 100
MAX_TEXT = 2000
MAX_SHORT = 120
#: The whole list as stored. The caps above bound one item each, and together
#: they allow about 200 MB (500 threads x 100 replies x 2,000 characters), far
#: past what a document's comments are for; the PUT refuses a list over this.
MAX_TOTAL = 1_000_000


def _text(value: Any, limit: int) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _reply(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    text = _text(raw.get("text"), MAX_TEXT)
    if not text.strip():
        return None
    return {"author": _text(raw.get("author"), MAX_SHORT), "at": _text(raw.get("at"), 40), "text": text}


def _thread(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    ident = _text(raw.get("id"), MAX_SHORT)
    if not ident:
        return None
    replies = raw.get("replies")
    kept = [r for r in (_reply(item) for item in replies[:MAX_REPLIES]) if r] if isinstance(replies, list) else []
    line = raw.get("line")
    return {
        "id": ident,
        "key": _text(raw.get("key"), MAX_SHORT),
        "author": _text(raw.get("author"), MAX_SHORT),
        "at": _text(raw.get("at"), 40),
        "text": _text(raw.get("text"), MAX_TEXT),
        "replies": kept,
        "resolved": raw.get("resolved") is True,
        "resolved_at": _text(raw.get("resolved_at"), 40),
        "target": _text(raw.get("target"), 400),
        "line": line if isinstance(line, int) and not isinstance(line, bool) and line > 0 else 1,
        "own": raw.get("own") is True,
    }


def clean(raw: Any) -> list[dict]:
    """The records that fit the shape, capped; anything else is dropped."""
    if not isinstance(raw, list):
        return []
    out = [t for t in (_thread(item) for item in raw[:MAX_THREADS]) if t]
    return out


def dump(threads: Any) -> str:
    """The column's text; an empty list is the empty string, as a new row has."""
    kept = clean(threads)
    return json.dumps(kept, separators=(",", ":")) if kept else ""


def too_large(threads: Any) -> bool:
    """Whether the list, once cleaned, would be stored over `MAX_TOTAL`."""
    return len(dump(threads)) > MAX_TOTAL


def load(stored: str | None) -> list[dict]:
    """The records a row holds. A row from before the column, or text that does
    not parse, reads as no threads rather than as an error on opening."""
    if not stored:
        return []
    try:
        return clean(json.loads(stored))
    except ValueError:
        return []
