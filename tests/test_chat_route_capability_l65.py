"""L65: the non-streaming /chat answers "can you search the web?" from the app's own list, model or none."""

from __future__ import annotations


def test_plain_chat_answers_a_capability_question_from_the_list(ai_client):
    body = ai_client.post("/chat", json={"question": "can you search the web?"}).json()
    assert "web" in body["ai_response"].lower()
    assert body["answered_by"] is None, "the list wrote it, not the model"
    assert body["raw_results"] == [], "a capability question searches nothing"
    stream = ai_client.post("/chat/stream", json={"question": "can you search the web?"})
    assert stream.status_code == 200


def test_plain_chat_still_sends_a_request_with_an_object_to_the_model(ai_client):
    body = ai_client.post("/chat", json={"question": "search the web for sourdough"}).json()
    assert body["answered_by"] is not None or body["ai_response"]
