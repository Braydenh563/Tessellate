"""Audit 1028 E16: a comparison of two named notes gave both sides the same
lines ("compare my biology note and my study plan"). The class: two sides whose
notes mention each other, so a sentence is picked for both, and a note whose
title holds both sides' words is claimed by both. Each note belongs to the side
its name opens with, and a line is said under one side, or as shared."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 11, 2, 12, 0)
SETS = {
    "plain": [
        "Biology revision. Cell respiration happens in the mitochondria. Glycolysis makes 2 ATP. Exam on 12 November covers chapters 4 to 6.",
        "Study plan for November: revise biology on Monday, chemistry on Wednesday, past papers on Friday. Aim for 2 hours a day.",
    ],
    "headed": [
        "# Biology\n\nCell respiration happens in the mitochondria. Glycolysis makes 2 ATP.\nMy study plan covers chapters 4 to 6.\nAim for 2 hours a day.",
        "# Study plan\n\nMonday: biology chapters 4 and 5.\nFriday: past papers and flashcards.\nAim for 2 hours a day.",
    ],
}


def _ask(client, question: str) -> str:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    text = ""
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event["delta"]
    return text


def _seed(session, monkeypatch, which: str) -> None:
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for i, content in enumerate(SETS[which]):
        entry = manager.create_entry(session, content)
        entry.created_at = entry.updated_at = datetime(2026, 10, 20 + i, 9, 0)
    session.commit()


def _bullets(text: str) -> list[str]:
    return [line.split(" [")[0].strip() for line in text.splitlines() if line.startswith("- ")]


@pytest.mark.parametrize("which", list(SETS))
@pytest.mark.parametrize(
    "question",
    [
        "compare my biology note and my study plan",
        "compare biology and study plan",
        "biology vs study plan",
        "what is the difference between my biology note and my study plan",
        "how does my biology note differ from my study plan",
    ],
)
def test_no_line_is_said_under_both_sides(client, session, monkeypatch, which, question):
    _seed(session, monkeypatch, which)
    said = _ask(client, question)
    bullets = _bullets(said)
    assert bullets, said
    assert len(bullets) == len(set(bullets)), said


@pytest.mark.parametrize("question", ["compare my biology note and my study plan", "biology vs study plan"])
def test_a_note_named_by_its_first_words_is_its_own_side(client, session, monkeypatch, question):
    _seed(session, monkeypatch, "plain")
    said = _ask(client, question)
    biology = said.split("**Study plan**")[0]
    study = said.split("**Study plan**")[1]
    assert "mitochondria" in biology and "mitochondria" not in study, said
    assert "chemistry" not in biology or "Together" in said or "Both" in said, said
