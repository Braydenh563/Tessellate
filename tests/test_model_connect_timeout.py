"""A model host that is off fails in seconds, not ten minutes (audit
2026-10-05, ARCH-17).

Both clients passed one float, 600, as `timeout`, which `requests` applies to
the connect as well as to each read: a LAN model host that is switched off
and drops packets held a chat turn, a filing job or a night-pass step for ten
minutes. The connect now has its own short limit; the answer keeps the long
one.
"""

from __future__ import annotations

from tests.fakes_http import FakeResponse

from tessellate.ai import ollama_client
from tessellate.ai import openai_client as openai_module


def test_openai_compatible_chat_connects_with_a_short_limit(monkeypatch, openai_client):
    seen = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):  # noqa: ANN001
        seen.append(timeout)
        return FakeResponse(payload={"choices": [{"message": {"content": "hi"}}]})

    monkeypatch.setattr("tessellate.ai.openai_client.requests.post", fake_post)
    openai_client.chat("m", [{"role": "user", "content": "hello"}])
    assert seen and seen[0] == (openai_module.CONNECT_TIMEOUT_SECONDS, 600.0)


def test_ollama_chat_connects_with_a_short_limit(monkeypatch):
    seen = []

    def fake_post(url, json=None, timeout=None, **_kwargs):  # noqa: ANN001
        seen.append(timeout)
        return FakeResponse(payload={"message": {"content": "hi"}})

    monkeypatch.setattr("tessellate.ai.ollama_client.requests.post", fake_post)
    client = ollama_client.OllamaClient(base_url="http://localhost:11434")
    monkeypatch.setattr(client, "runtime_options", lambda model, mode=None: {})
    monkeypatch.setattr(client, "request_extras", lambda mode, model: {})
    client.chat("m", [{"role": "user", "content": "hello"}])
    connect, read = seen[0]
    assert connect == ollama_client.CONNECT_TIMEOUT_SECONDS <= 10
    assert read == 600.0
