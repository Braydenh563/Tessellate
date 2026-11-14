"""Notes written over time, compared (CHAT_PLAN U11, A7): "compare this month with last month",
"am I writing more than last month", "which month did I write the most".

Two counts over two windows, both numbers in one measured line; the windows are read by `recognise` (the
one reader of dates), the counts are `Entry.created_at` rows. None when the question asks none of this.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import recognise
from tessellate.core.database import Entry

_CUE = re.compile(r"\b(?:compare|comparison|versus|vs\.?|more|less|fewer|than|against)\b")
_MOST = re.compile(r"\bwhich\s+(month|week|year)\b.*\b(?:most|busiest|more than any)\b|\b(?:busiest|most active)\s+(month|week|year)\b")


def _spans(text: str, now: datetime) -> list:
    return [f for f in recognise.recognise(text, now=now, tense="past") if not f.rank and f.kind in ("date", "range")]


def _between(session: Session, stat, window) -> int:  # noqa: ANN001
    return session.scalar(stat._visible(select(func.count(Entry.id)).where(Entry.created_at >= window[0], Entry.created_at <= window[1]))) or 0


def answer(text: str, session: Session, now: datetime):  # noqa: ANN201
    """A `StatAnswer` for a compare or a busiest-period question, else None."""
    from tessellate.ai import notebook_stats as stat

    most = _MOST.search(text)
    if most:
        return _busiest(session, stat, most.group(1) or most.group(2), now)
    if not _CUE.search(text) or not (re.search(r"\b(?:compare|comparison|versus|vs\.?)\b", text) or re.search(r"\b(?:notes?|write|writing|wrote|written)\b", text)):
        return None
    spans = _spans(text, now)
    if len(spans) == 1 and spans[0].kind == "range" and re.search(r"\b(?:more|less|fewer)\b.*\bthan\b", text):
        grain = spans[0].value[2]
        spans = [*(_spans(f"this {grain}", now)[:1]), spans[0]]
    windows = [(f.text.strip(), stat._window(f.text.strip())) for f in spans[:2]]
    if len(windows) < 2 or any(w is None for _t, w in windows):
        return None
    (a_words, a), (b_words, b) = windows
    a_n, b_n = _between(session, stat, a), _between(session, stat, b)
    return stat.StatAnswer(
        "window-compare",
        f"You wrote {stat._plural(a_n, 'note')} {a_words} and {b_n} {b_words}.",
        [{"label": a_words, "count": a_n}, {"label": b_words, "count": b_n}],
    )


def _busiest(session: Session, stat, grain: str, now: datetime):  # noqa: ANN001, ANN201
    keys = {"month": "%Y-%m", "week": "%G-W%V", "year": "%Y"}
    counts = Counter(made.strftime(keys[grain]) for (made,) in session.execute(stat._visible(select(Entry.created_at))) if made)
    if not counts:
        return None
    key, n = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    first = datetime.strptime(key + ("-1" if grain == "week" else ""), {"month": "%Y-%m", "week": "%G-W%V-%u", "year": "%Y"}[grain])
    said = {"month": f"{first:%B %Y}", "week": f"the week of {first.day} {first:%B %Y}", "year": f"{first:%Y}"}[grain]
    return stat.StatAnswer("busiest-period", f"You wrote the most in {said}: {stat._plural(n, 'note')}.", [{"label": said, "count": n}])
