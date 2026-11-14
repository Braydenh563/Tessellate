"""L-chat-8: "do my notes contradict each other" lists the subjects a newer
note changed (`supersede.changes`, the same pairing the composer uses to
answer from the current note) beside the insights reader's dated changes of
mind, and the imperative wordings ("look for inconsistencies in my notes",
"check for inconsistencies") reach the same answer instead of the
no-model tool line."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import supersede

NOW = dt.datetime(2026, 11, 10, 10, 0, 0)

NOTES = [
    {"id": 1, "content": "My address is 12 Oak Street", "created_at": "2025-03-01"},
    {"id": 2, "content": "My address is now 4 Birch Road", "created_at": "2026-06-01"},
    {"id": 3, "content": "Golf on Sunday with Sam", "created_at": "2026-06-02"},
    {"id": 4, "content": "Uni days this semester: Tuesday and Thursday", "created_at": "2026-02-20"},
    {"id": 5, "content": "Uni days this semester are Monday and Wednesday", "created_at": "2026-07-01"},
]


def test_changes_pairs_each_subject_a_newer_note_replaced():
    found = supersede.changes(NOTES)
    pairs = {(r.older["id"], r.newer["id"]) for r in found}
    assert pairs == {(1, 2), (4, 5)}, pairs


def test_a_label_two_different_notes_share_is_not_a_change_of_mind():
    """Two recipes each list "Ingredients:": different things, not one thing at two times."""
    recipes = [
        {"id": 1, "content": "Lasagne\nIngredients: beef mince, lasagne sheets, passata", "created_at": "2026-09-22"},
        {"id": 2, "content": "Banana bread\nIngredients: 3 ripe bananas, 250 g flour, 2 eggs", "created_at": "2026-10-18"},
        {"id": 3, "content": "Banana bread\nIngredients: 4 ripe bananas, 250 g flour, 2 eggs", "created_at": "2026-10-25"},
    ]
    assert [(r.older["id"], r.newer["id"]) for r in supersede.changes(recipes)] == [(2, 3)]


def test_changes_leaves_one_note_and_undated_notes_alone():
    assert supersede.changes(NOTES[:1]) == []
    assert supersede.changes([{**n, "created_at": ""} for n in NOTES]) == []


def _add(session, content: str, day: str) -> None:
    from tessellate.core.database import Entry

    session.add(Entry(content=content, created_at=dt.datetime.fromisoformat(day + "T09:00:00")))


def _say(session, question: str) -> str:
    from tessellate.api import chat_extra

    events = chat_extra.notebook_events(session, question, now=NOW)
    assert events and events[0]["type"] == "answer", question
    return events[0]["delta"]


def test_the_contradiction_answer_names_the_old_and_the_new_value(session):
    for note in NOTES:
        _add(session, note["content"], note["created_at"])
    session.commit()
    said = _say(session, "do my notes contradict each other")
    assert "4 Birch Road" in said and "12 Oak Street" in said, said
    assert "Monday and Wednesday" in said and "Tuesday and Thursday" in said, said
    assert "- Your address: your note of 1 June says 4 Birch Road, and an older one, from 1 March 2025, said 12 Oak Street." in said, said
    assert "no change of mind" not in said, said


@pytest.mark.parametrize("question", [
    "look for inconsistencies in my notes", "check for inconsistencies", "check my notes for contradictions",
    "find contradictions in my notes", "are there inconsistencies in my notes", "scan my notes for conflicts",
])
def test_imperative_wordings_reach_the_contradiction_answer(session, question):
    said = _say(session, question)
    assert "change of mind" in said, said


@pytest.mark.parametrize("question", ["does the dentist conflict with work", "my plans conflict with the dentist", "check for updates"])
def test_a_clash_with_a_thing_is_not_the_contradiction_answer(session, question):
    from tessellate.api import chat_extra

    events = chat_extra.notebook_events(session, question, now=NOW) or [{"delta": ""}]
    assert "change of mind" not in events[0]["delta"], question
