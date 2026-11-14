"""L254: "what are my goals" and "show my lists" are a list answer from the notes
tagged or titled goal or list, composed without a model."""

from __future__ import annotations

import pytest

QUESTIONS = {
    "goal": ["what are my goals", "What are my goals?", "show my goals", "list my goals"],
    "list": ["show my lists", "what are my lists?", "show me my lists"],
}


@pytest.fixture()
def notebook(ai_client, fake_ollama):
    fake_ollama.running = False
    ids = {}
    ids["tagged goal"] = ai_client.post("/entries", json={"content": "Run a half marathon by June", "tags": ["goal"]}).json()["id"]
    ids["titled goals"] = ai_client.post("/entries", json={"content": "# Goals 2026\n- learn Spanish\n- read twelve books"}).json()["id"]
    ids["titled list"] = ai_client.post("/entries", json={"content": "Shopping list\n- eggs\n- flour"}).json()["id"]
    ids["tagged list"] = ai_client.post("/entries", json={"content": "Packing for Lisbon\n- passport", "tags": ["list"]}).json()["id"]
    ids["other"] = ai_client.post("/entries", json={"content": "Gym went well today."}).json()["id"]
    return ids


def _ask(client, question):
    return client.post("/chat", json={"question": question}).json()


@pytest.mark.parametrize("question", QUESTIONS["goal"])
def test_goals_come_from_notes_tagged_or_titled_goal(ai_client, notebook, question):
    body = _ask(ai_client, question)
    shown = {r["id"] for r in body["raw_results"]}
    assert {notebook["tagged goal"], notebook["titled goals"]} <= shown
    assert notebook["other"] not in shown and notebook["titled list"] not in shown
    assert "Goals 2026" in body["ai_response"]
    assert body["ai_response"].count("\n- ") >= 2, "a list answer, one line a note"


@pytest.mark.parametrize("question", QUESTIONS["list"])
def test_lists_come_from_notes_tagged_or_titled_list(ai_client, notebook, question):
    body = _ask(ai_client, question)
    shown = {r["id"] for r in body["raw_results"]}
    assert {notebook["titled list"], notebook["tagged list"]} <= shown
    assert notebook["other"] not in shown and notebook["tagged goal"] not in shown
    assert body["ai_response"].count("\n- ") >= 2
