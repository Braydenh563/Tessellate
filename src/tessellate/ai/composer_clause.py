"""The rest of a prose sentence after the words a source gave (L26)."""

from __future__ import annotations

import re

_TAIL = re.compile(r"[,;][^\n]*?(?=[.!?](?:\s|$)|\n|$)")


def trailing_clause(whole: str, sentence: str) -> str:
    """The clause after a comma ("$200" then ", a gap of about $30 between them"):
    the mark follows the whole sentence, not the words the source gave (E51)."""
    at = whole.find(sentence) if sentence else -1
    tail = _TAIL.match(whole, at + len(sentence)) if at >= 0 else None
    return tail.group(0) if tail else ""
