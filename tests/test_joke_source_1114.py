"""The owner's bug (CHAT_PLAN 2026-10-10 list, L-chat-19): "it got jokes from
another note but not the separate one from the top of the matching records".
A joke is said from the note the answer names, and the note it names is the
one at the top of the matching records."""

from __future__ import annotations

import re
from datetime import date, datetime

import pytest

from tests import _seed_1031c as seed_c

JOKES = [
    ("Chicken joke\n\nWhy did the chicken join a band? Because it had the drumsticks", "2026-10-02T10:00:00"),
    ("Jokes I like\n\n- Why don't skeletons fight? They don't have the guts\n- What do you call a fake noodle? An impasta", "2026-09-12T10:00:00"),
]
PUNCHLINES = ("drumsticks", "guts", "impasta")


@pytest.fixture
def ask(client, session, monkeypatch):
    from tessellate.entry import manager

    ids = []
    for content, when in JOKES:
        entry = manager.create_entry(session, content, category_name="Fun", tags=["jokes"])
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
        ids.append(entry.id)
    session.commit()
    return seed_c.asker(client, monkeypatch), ids


def _named(events) -> list[int]:
    return [int(r["note_id"]) for e in events if e.get("type") == "grounding" for r in e.get("sentences") or [] if r.get("note_id") is not None]


def _matching(events) -> list[int]:
    return [int(r["id"]) for e in events if e.get("type") == "meta" for r in e.get("raw_results") or []]


@pytest.mark.parametrize("question", ["tell me a joke", "tell me one of my jokes", "make me laugh", "tell me a joke from my notes"])
def test_a_joke_is_said_from_the_top_matching_record(ask, question):
    go, ids = ask
    said, events = go(question)
    contents = {i: JOKES[n][0] for n, i in enumerate(ids)}
    told = [p for p in PUNCHLINES if p in said]
    assert told, said
    named = _named(events) or [int(n) for n in re.findall(r"#/notes/(\d+)", said)]
    assert named, said
    #: Every punchline said lives in a note the answer names (its source is visible and checked).
    for punchline in told:
        assert any(punchline in contents[i] for i in named if i in contents), (punchline, named, said)
    #: And when the notes were searched, the note said is the top matching record.
    matching = _matching(events)
    if matching:
        assert named[0] == matching[0], (named, matching, said)


@pytest.mark.parametrize(("question", "said", "not_said"), [
    ("tell me one of my jokes", "drumsticks", "guts"),
    ("tell me the skeleton joke", "guts", "impasta"),
    ("tell me the noodle joke", "impasta", "guts"),
    ("tell me the chicken joke", "drumsticks", "guts"),
])
def test_the_joke_asked_for_is_the_one_said(question, said, not_said):
    from tessellate.ai import composer_digest

    text = composer_digest.answer(question, _NOTES, today=TODAY)["text"]
    assert said in text and not_said not in text, text


@pytest.mark.parametrize("question", ["what jokes have I saved", "what are my jokes"])
def test_every_joke_is_said_when_all_are_asked_for(question):
    from tessellate.ai import composer_digest

    text = composer_digest.answer(question, _NOTES, today=TODAY)["text"]
    assert all(p in text for p in PUNCHLINES), text
    #: A listed joke keeps its own capital and is never run into the next one's question.
    assert "the guts What" not in text and "and what do you call" not in text, text
    assert "“What do you call a fake noodle? An impasta”" in text, text


TODAY = date(2026, 10, 12)
_NOTES = [
    {"id": n + 1, "content": content, "created_at": when, "category": "Fun", "tags": ["jokes"]}
    for n, (content, when) in enumerate(JOKES)
]
