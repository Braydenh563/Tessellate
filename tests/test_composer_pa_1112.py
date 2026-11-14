"""Composer batch A of PR 216 (ledger 1112): the Co1, composer-acts, -asks, -chat,
-chips, -dialogue and -parity rows. No model; clocks are fixed by the seeds.

One section per row id, in the order they were built."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tests._app_js import app_js_text

FRAME = {"note_ids": [], "subject": "dentist", "person": "", "ask": "when is the dentist", "dates": ["2026-11-04"], "items": []}


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


def say(go, *questions):
    """The last answer of a chat that asked `questions` one after another, history carried."""
    history: list[dict] = []
    text = ""
    for question in questions:
        text, _events = go(question, history=history or None)
        history.append({"question": question, "answer": text})
    return text


# --- O4: the frame is saved with the chat ------------------------------------------


def test_o4_a_saved_turn_keeps_its_frame_and_objects(client):
    made = client.post(
        "/conversations",
        json={"question": "when is the dentist", "answer": "On 4 November.", "frame": FRAME, "objects": ["Dentist"]},
    )
    assert made.status_code in (200, 201), made.text
    full = client.get(f"/conversations/{made.json()['id']}").json()
    reply = full["messages"][1]
    assert reply["frame"]["subject"] == "dentist" and reply["frame"]["dates"] == ["2026-11-04"], reply
    assert reply["objects"] == ["Dentist"]


def test_o4_a_frame_is_bounded_like_the_live_one(client):
    bad = dict(FRAME, dates=["not a day"] * 3 + ["2026-11-04"], subject="x" * 500)
    made = client.post("/conversations", json={"question": "q", "answer": "a", "frame": bad})
    assert made.status_code == 422, made.text


def test_o4_a_turn_without_one_saves_as_before(client):
    made = client.post("/conversations", json={"question": "q", "answer": "a"})
    reply = client.get(f"/conversations/{made.json()['id']}").json()["messages"][1]
    assert "frame" not in reply and "objects" not in reply


def test_o4_the_page_sends_and_restores_it():
    js = app_js_text()
    assert "frame: t.turnFrame," in js, "chat-turn persist sends the frame"
    assert "frame: message.frame" in js and "objects: message.objects" in js, "a reopened chat puts the frame back on its turns"


# --- O4 / L239: "and the dentist" keeps the ask of the answer before it ------------


def _two_turns(go, first):
    history: list[dict] = []
    text, events = go(first)
    history.append({"question": first, "answer": text, **({"frame": f} if (f := next((e["frame"] for e in events if e.get("type") == "frame"), None)) else {})})
    text, events = go("and the dentist", history=history)
    return text, next((e["frame"] for e in events if e.get("type") == "frame"), {})


@pytest.mark.xfail(strict=True, reason="'and the dentist' reads as a new topic ('There are two notes about dentist'), not the 'when' of the answer before (L239 reopened; LEDGER L-chat-9)")
@pytest.mark.parametrize("first", ["when is the passport renewal", "when is the atlas beta"])
def test_l239_and_the_dentist_keeps_the_when_of_the_answer_before(go, first):
    text, frame = _two_turns(go, first)
    assert "4 November 2026" in text, text
    assert frame.get("dates") == ["2026-11-04"], frame
