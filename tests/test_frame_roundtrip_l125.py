"""L125: the F1 frame is saved with a chat and read back on reopen, and its subject is a
noun phrase, never the question's own verb ("book am I reading")."""

from datetime import date

import pytest

from tessellate.ai import composer_dialogue

FRAME = {
    "note_ids": [3, 4],
    "subject": "kitchen budget",
    "person": "Sam",
    "ask": "what is the kitchen budget",
    "dates": ["2026-11-10"],
    "items": ["tiles", "paint"],
}


def test_frame_survives_save_and_reopen(client):
    made = client.post("/conversations", json={"question": "q1", "answer": "a1"}).json()
    client.post(
        f"/conversations/{made['id']}/turns",
        json={"question": "kitchen budget?", "answer": "About 4k.", "frame": FRAME, "objects": ["Kitchen budget"]},
    )
    full = client.get(f"/conversations/{made['id']}").json()
    assistant = full["messages"][-1]
    assert assistant["frame"] == FRAME
    assert assistant["objects"]
    assert "frame" not in full["messages"][1]  # the first, frameless turn stays as it was


def test_empty_frame_is_not_stored(client):
    made = client.post("/conversations", json={"question": "q1", "answer": "a1"}).json()
    client.post(
        f"/conversations/{made['id']}/turns",
        json={"question": "hi", "answer": "Hello.", "frame": {"note_ids": [], "subject": ""}},
    )
    assert "frame" not in client.get(f"/conversations/{made['id']}").json()["messages"][-1]


@pytest.mark.parametrize(
    ("asked", "subject"),
    [
        ("What book am I reading?", "book reading"),
        ("what's left on my todo list?", "todo list"),
        ("how much did the flights to Kyoto cost?", "flights to Kyoto cost"),
        ("when is the dentist appointment", "dentist appointment"),
    ],
)
def test_frame_subject_is_a_noun_phrase(asked, subject):
    result = {"text": "x", "grounding": [{"note_id": 1}]}
    notes = [{"source_id": 1, "title": "Note"}]
    frame = composer_dialogue.turn_frame(asked, result, notes, date(2026, 11, 10))
    assert frame["subject"].lower() == subject.lower()
