"""L-chat-219, 220, 221 (CHAT_PLAN section 7's rows 3, 4 and 5), measured on the
R9 notebook (50 notes, clock Monday 9 November 2026), no model:
219 the week's summary is non-empty and every quotation in it is a span of a note;
220 a miss never says a bare "Nothing in the notes" and always offers a way on;
221 an answer takes under one second at 96 notes (best of three, so a busy
machine does not fail it)."""

from __future__ import annotations

import re
import time

import pytest

import tests._seed_r9_1109 as sd
from tessellate.entry import manager

MISSES = [
    "tell me about zebra crossings", "anything about quantum gravity", "what about my llama farm", "when is my yoga class",
    "who is Bartholomew", "notes on volcanoes", "what do I know about submarines", "where did I put the spare key",
    "do I have anything on cryptography", "what is in my note about the lighthouse",
]
FAST = ["summarise my week", "what is 15% of 240", "convert 5 miles to km", "how many days until Christmas", "what did I write about the kitchen"] + MISSES[:4]


@pytest.fixture
def go(client, session, monkeypatch):
    sd.seed(session)
    return sd.asker(client, monkeypatch, chat=True), session


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_`#]", "", text)).lower()


def test_the_weeks_summary_quotes_only_spans_of_the_notes(go) -> None:
    ask, _ = go
    text, _events = ask("summarise my week")
    assert text.strip()
    corpus = _norm(" ".join(f"{title or ''} {body}" for title, body, _ in sd.NOTES))
    quoted = re.findall(r"“([^”]+)”", text)
    assert quoted, text
    for span in quoted:
        assert _norm(span.rstrip("….")) in corpus, span
    for title in re.findall(r"\*\*([^*]+)\*\*", text):
        assert _norm(title) in corpus, title


def test_no_miss_is_a_bare_nothing_in_the_notes(go) -> None:
    ask, _ = go
    bare = []
    for question in MISSES:
        text, _events = ask(question)
        said = text.strip()
        if re.fullmatch(r"nothing in (?:the|your) notes\.?", said, re.I) or not (("?" in said) or "try" in said.lower() or "can also" in said.lower() or "web search" in said.lower()):
            bare.append((question, said[:80]))
    assert not bare, bare


def test_an_answer_takes_under_a_second_at_96_notes(go) -> None:
    ask, session = go
    for n in range(46):
        manager.create_entry(session, f"# Filler {n}\n\nNote {n} about topic{n % 9}: a few words to search through, number {n * 7}.", category_name="Uncategorised")
    session.commit()
    ask("hello there")  # first call loads the lazy modules
    slow = {}
    for question in FAST:
        best = min(_timed(ask, question) for _ in range(3))
        if best >= 1.0:
            slow[question] = round(best, 3)
    assert not slow, slow


def _timed(ask, question: str) -> float:
    start = time.perf_counter()
    ask(question)
    return time.perf_counter() - start
