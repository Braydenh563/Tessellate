"""Audit 1030 A39 to A41: slow, noisy and overflowing routes."""

from __future__ import annotations

import time

import pytest

from tessellate.api import routes_insights


def test_a_hung_model_never_holds_the_greeting(ai_client, fake_ollama, monkeypatch):
    """A39: 4,005 ms with a hung chat model; now the composed greeting inside the wait."""
    monkeypatch.setattr(routes_insights, "GREETING_WAIT", 0.2)
    monkeypatch.setattr(routes_insights, "_GREETING_FLIGHT", {})
    release = []

    def hung(*args, **kwargs):  # noqa: ANN002, ANN003
        while not release:
            time.sleep(0.02)
        return {"content": "Rise and shine"}

    monkeypatch.setattr(fake_ollama, "chat", hung)
    started = time.monotonic()
    body = ai_client.get("/insights/greeting?block=morning").json()
    assert time.monotonic() - started < 2.0
    assert body["source"] in ("composed", "fallback")
    #: While the first call still runs a second request waits for nothing.
    started = time.monotonic()
    again = ai_client.get("/insights/greeting?block=morning").json()
    assert time.monotonic() - started < 1.0 and again["source"] in ("composed", "fallback")
    release.append(1)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and not routes_insights._GREETING_FLIGHT["morning"].done():
        time.sleep(0.02)
    #: The late greeting is served by the next request, once.
    late = ai_client.get("/insights/greeting?block=morning").json()
    assert late["source"] == "ai" and late["greeting"] == "Rise and shine"


def test_help_ask_with_the_model_call_cut_answers_from_the_help(ai_client, monkeypatch):
    """A40: a stopped model call is not an ASGI exception."""
    from tessellate.ai import help_chat
    from tessellate.ai.provider import ProviderError

    def cut(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ProviderError("The model call was stopped.")

    monkeypatch.setattr(help_chat, "answer", cut)
    response = ai_client.post("/help/ask", json={"question": "how do I tag a note"})
    assert response.status_code == 200
    assert response.json()["content"]


@pytest.mark.parametrize("path", [
    "/conversations/99999999999999999999", "/conversations/9223372036854775808", "/ask-history/99999999999999999999",
    "/entries/9223372036854775808", "/ask-history?offset=9223372036854775808", "/conversations?offset=99999999999999999999",
])
def test_a_number_above_the_store_is_refused_never_a_500(client, path):
    """A41."""
    response = client.get(path)
    assert response.status_code in (404, 422), (path, response.status_code)


@pytest.mark.parametrize(("method", "path"), [
    ("DELETE", "/conversations/99999999999999999999"), ("PUT", "/conversations/99999999999999999999/archive"),
    ("PUT", "/conversations/99999999999999999999/unarchive"), ("POST", "/conversations/99999999999999999999/fork"),
    ("DELETE", "/conversations/99999999999999999999/turns/0"), ("DELETE", "/ask-history/99999999999999999999"),
])
def test_a_write_to_a_number_above_the_store_is_refused(client, method, path):
    response = client.request(method, path, json={} if method in ("POST", "PUT") else None)
    assert response.status_code in (404, 422), (method, path, response.status_code)


def test_calc_in_chat_answers_what_the_dialog_answers(client):
    """A28: "/calc 12% of 340" is 40.8 in Chat as it is in the Calculator."""
    import json

    def said(question):
        out = ""
        with client.stream("POST", "/chat/stream", json={"question": question}) as response:
            for line in response.iter_lines():
                if line.strip():
                    event = json.loads(line)
                    out += event.get("delta", "") if event["type"] == "answer" else ""
        return out

    text = said("/calc 12% of 340")
    assert "40.8" in text and "I can only work out sums" not in text
    assert "I can only work out sums" in said("/calc banana split")
    assert "7" in said("/calc 3 + 4")
