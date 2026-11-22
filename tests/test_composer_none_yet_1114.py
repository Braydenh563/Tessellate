"""L-chat-233: the "none yet" lines of the part-of-an-overview follow-ups ("what are those tags") were fixed text;
they are composed now, in the chat's voice, and each still says the plain fact."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_talk

TODAY = date(2026, 11, 14)
OVERVIEW = [{"question": "statistics", "answer": "You have 0 notes.\n\nOpen Statistics for the full picture?"}]
KEY = {"tags": ("what are those distinct tags", ("tag",)), "categories": ("what are those categories", ("categor", "filed", "filing", "nothing")), "documents": ("what are those documents", ("document", "uploaded"))}


def _said(session, question: str, voice: str) -> str:
    events = composer_talk.reply(session, question, OVERVIEW, TODAY, voice=voice)
    assert events, question
    return events[0]["delta"]


@pytest.mark.parametrize("what", sorted(KEY))
def test_the_none_yet_line_is_composed_and_says_none(session, what):
    question, stem = KEY[what]
    seen = {_said(session, question + suffix, voice) for voice in ("natural", "professional", "terse", "playful") for suffix in ("", "?", "??", " please", " now")}
    assert len(seen) >= 4, seen
    assert all(any(w in s.lower() for w in stem) for s in seen), seen
    assert not any("!" in s or chr(0x2014) in s for s in seen)
