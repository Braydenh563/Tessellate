"""The records a broad overview reads beyond the notes that say its word (L-chat-37).

"What else do my notes say about university?" over five records quoted one
note twice: the digest kept only the notes holding "university", so "I'm
taking one IT subject and three Design subjects" (about uni, without the
word) never reached the answer.
"""

from __future__ import annotations

import re
from datetime import date

#: The search's own "closely by meaning" (`composer_frame`, 0.75 and up).
_CLOSE = 0.75
#: "what (else) do my notes say about uni", "what do I know about uni".
_SAY_ABOUT = re.compile(r"\bwhat (?:else )?(?:do|does|did) (?:my|the) (?:notes|entries) (?:say|tell me|have|mention|know|cover)\b|\bwhat (?:else )?do i know (?:about|on)\b", re.I)


def close_by_meaning(kind: str, question: str, views: list, members: list) -> list:
    """A broad "what do my notes say about X" reads every record the search
    found close by meaning, not only the notes that say X's word (L-chat-37:
    "I'm taking one IT subject and three Design subjects" is about uni without
    the word, and the answer quoted one note twice instead)."""
    if kind != "overview" or not members or not _SAY_ABOUT.search(question):
        return members
    have = {v.id for v in members}
    close = [v for v in views if v.id not in have and _match_score(v) >= _CLOSE]
    return members + sorted(close, key=lambda v: (v.written or date.min, v.rank))


def _match_score(view) -> float:  # noqa: ANN001
    info = view.note.get("match_info") or {}
    return float(info.get("score") or 0) if info.get("type") in ("semantic", "hybrid") else 0.0
