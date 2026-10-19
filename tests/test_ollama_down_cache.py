"""A refused Ollama is remembered for a few seconds, so a turn makes one
connect attempt rather than one per stage (Windows: ~2 s per refusal on
`localhost`, owner log 2026-10-19). Fake clock, no sleeps."""
import pytest
import requests

from tessellate.ai import ollama_client
from tessellate.ai.ollama_client import OllamaClient, OllamaError


@pytest.fixture()
def attempts(monkeypatch, app_state):
    calls: list[str] = []
    now = [1000.0]

    def refuse(method, url, **kwargs):
        calls.append(url)
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(requests, "request", refuse)
    monkeypatch.setattr(ollama_client, "_clock", lambda: now[0])
    ollama_client._down_until.clear()
    yield calls, now
    ollama_client._down_until.clear()


def test_a_turn_with_ollama_down_connects_once(attempts):
    calls, _ = attempts
    client = OllamaClient()
    assert client.is_running() is False
    assert client.is_running() is False
    assert client.show("m") == {}
    with pytest.raises(OllamaError):
        client.embed("nomic", "x")
    with pytest.raises(OllamaError):
        client.chat("m", [{"role": "user", "content": "hi"}])
    assert len(calls) == 1


def test_the_down_state_expires_(attempts):
    calls, now = attempts
    client = OllamaClient()
    client.is_running()
    now[0] += ollama_client.DOWN_TTL_SECONDS + 0.1
    client.is_running()
    assert len(calls) == 2


def test_connect_timeout_is_short():
    assert ollama_client.CONNECT_TIMEOUT_SECONDS <= 1.0
