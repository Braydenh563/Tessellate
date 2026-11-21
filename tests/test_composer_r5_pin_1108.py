"""Composer round 5, 2026-11-08 (pin): rows of audits 1107 (D, E, R3) that round 4 left unfixed. Every
question runs through `/chat/stream` with no model and a fixed clock, because the seams these
rows share (the pool the route builds, the act cues, the history) sit in front of the composer."""

from __future__ import annotations


import pytest

from tessellate.entry import manager

from tests import _r5_1108 as r5



@pytest.fixture
def ask(client, session, monkeypatch):
    return r5.driver(client, session, monkeypatch)


@pytest.mark.parametrize("question, title", [("pin the Gym note", "Gym"), ("favourite the Gym note", "Gym"), ("pin the Sara note", "Sara"), ("unpin the Gym note", "Gym")])
def test_d2_an_exact_title_is_the_note_not_a_question(ask, question, title):
    said = ask(question)["text"]
    assert "Which note" not in said and f"“{title}”" in said, said


def test_d2_two_notes_with_the_same_exact_title_still_ask(ask, session):
    manager.create_entry(session, "# Gym\n\nA second note with the same title.", category_name="Uncategorised")
    session.commit()
    assert "Which note" in ask("pin the Gym note")["text"]
