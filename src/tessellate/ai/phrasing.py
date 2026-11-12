"""Which of a family of phrasings to say, so replies do not sound canned.

The owner, 2026-10-11: "can it have more varied responses??". Every family
of replies (greetings, calls, thanks, nothing found, clarifying questions,
offers, openers) holds eight phrasings or more, and `choose` picks one that
opens unlike each of the last three replies in the conversation and, where
it can, is shaped unlike the last (a question after a statement, a short
line after a long one). The pick is a hash of the key and the seed, so a
test or a replayed conversation gets the same words every time.

`opener`, `shape`, `opener_ratio` and `shape_variety` are the measures the
gold eval floors (`tests/test_reply_variety.py`).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from tessellate.core.lazyre import lazy_compile

#: How many earlier replies a pick must not echo.
RECENT = 3
_WORDS = lazy_compile(r"[a-z']+")
_SENTENCE = lazy_compile(r"[.?]\s+(?=[A-Z])")


def opener(text: str) -> str:
    """The first two words, lowered: what makes two replies sound alike."""
    return " ".join(_WORDS.findall((text or "").lower())[:2])


def shape(text: str) -> tuple[int, bool, int]:
    """Sentences (1, 2, 3 or more), whether it asks, and its length (short,
    middling, long): three replies of one shape in a row read as a form."""
    text = (text or "").strip()
    sentences = min(3, len(_SENTENCE.split(text)) if text else 0)
    size = 0 if len(text) < 30 else 1 if len(text) < 75 else 2
    return sentences, text.endswith("?"), size


def _alike(option: str, reply: str) -> bool:
    reply = (reply or "").strip()
    return bool(reply) and (reply.startswith(option) or opener(option) == opener(reply))


def _fresh(options: list[str], recent: list[str]) -> list[str]:
    """The options unlike the recent replies, and of another shape than the
    last one when any is; all of them when none is."""
    fresh = [o for o in options if not any(_alike(o, r) for r in recent)]
    if not fresh:
        fresh = [o for o in options if not any((r or "").strip().startswith(o) for r in recent)] or options
    if recent:
        last = shape(recent[-1])
        fresh = [o for o in fresh if shape(o) != last] or fresh
    return fresh


def choose(options: Sequence[str], key: str, recent: Sequence[str] = (), seed: str = "") -> str:
    """One of `options` for `key` (the message and the family), unlike the
    last `RECENT` replies in `recent` (oldest first). Deterministic: the
    same key, seed and recent replies give the same line."""
    options = list(options)
    if not options:
        return ""
    recent = [r for r in recent if r][-RECENT:]
    fresh = _fresh(options, recent)
    digest = hashlib.sha1(f"{key.strip().lower()}|{seed}|{len(recent)}".encode()).digest()
    return fresh[int.from_bytes(digest[:4], "big") % len(fresh)]


def opener_ratio(replies: Sequence[str], window: int = RECENT + 1) -> float:
    """The share of distinct openers in every run of `window` replies,
    averaged: 1.0 when no reply opens like any of the three before it."""
    runs = [replies[i : i + window] for i in range(len(replies) - window + 1)]
    if not runs:
        return 1.0
    return sum(len({opener(r) for r in run}) / len(run) for run in runs) / len(runs)


def shape_variety(replies: Sequence[str]) -> float:
    """The share of replies shaped unlike the one before."""
    pairs = list(zip(replies, replies[1:], strict=False))
    if not pairs:
        return 1.0
    return sum(shape(a) != shape(b) for a, b in pairs) / len(pairs)


def repeats(replies: Sequence[str]) -> int:
    """Replies that say a line one of the last `RECENT` said."""
    return sum(1 for i, r in enumerate(replies) if r in replies[max(0, i - RECENT) : i])
