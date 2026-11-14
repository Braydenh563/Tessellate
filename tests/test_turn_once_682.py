"""A chat send runs once per `turn_id` (E70, L682): the same id posted again
gets the first result back and the model is not asked a second time."""

from __future__ import annotations

import pytest

from tessellate.ai import turn_once
from tessellate.api import routes_chat


@pytest.fixture(autouse=True)
def _fresh():
    turn_once.reset_for_tests()
    yield
    turn_once.reset_for_tests()


def test_a_repeated_post_with_the_same_turn_id_runs_once(ai_client, monkeypatch):
    ran = []
    real = routes_chat._check_refs

    def counted(session, body):
        ran.append(body.question)
        return real(session, body)

    monkeypatch.setattr(routes_chat, "_check_refs", counted)
    body = {"question": "What jokes have I saved?", "turn_id": "turn-0001-abcd"}
    first = ai_client.post("/chat", json=body)
    again = ai_client.post("/chat", json=body)
    assert first.status_code == again.status_code == 200
    assert again.json() == first.json()
    assert ran == ["What jokes have I saved?"]


def test_a_new_turn_id_or_none_runs_again(ai_client, monkeypatch):
    ran = []
    real = routes_chat._check_refs
    monkeypatch.setattr(routes_chat, "_check_refs", lambda session, body: ran.append(1) or real(session, body))
    ai_client.post("/chat", json={"question": "hello there", "turn_id": "turn-0001-abcd"})
    ai_client.post("/chat", json={"question": "hello there", "turn_id": "turn-0002-abcd"})
    ai_client.post("/chat", json={"question": "hello there"})
    ai_client.post("/chat", json={"question": "hello there"})
    assert len(ran) == 4


def test_a_repeated_stream_replays_the_first_lines(ai_client, monkeypatch):
    ran = []
    real = routes_chat._answer_lines

    def counted(req):
        ran.append(1)
        return real(req)

    monkeypatch.setattr(routes_chat, "_answer_lines", counted)
    body = {"question": "hello there", "turn_id": "turn-0003-abcd"}
    first = ai_client.post("/chat/stream", json=body)
    again = ai_client.post("/chat/stream", json=body)
    assert first.status_code == again.status_code == 200
    assert again.text == first.text and first.text
    assert len(ran) == 1


def test_a_turn_id_that_is_not_an_id_is_refused(ai_client):
    bad = ai_client.post("/chat", json={"question": "hi", "turn_id": "no spaces allowed!"})
    assert bad.status_code == 422
