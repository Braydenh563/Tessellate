"""Q11 (owner 2026-11-11): the liveness probe is believed for 30 s, any failed
request drops it, and seeing Ollama answer (the model status poll, a start)
drops the refused and silent marks at once, so the composer never answers as
if the model were off in the window after Ollama starts. Fake clock."""
import pytest

from tessellate.ai import ollama_client
from tessellate.ai.ollama_client import OllamaClient

BASE = "http://127.0.0.1:9"


@pytest.fixture()
def clock(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(ollama_client, "_clock", lambda: now[0])
    ollama_client._down_until.clear()
    yield now
    ollama_client._down_until.clear()


def test_the_up_window_is_thirty_seconds():
    assert ollama_client.UP_TTL_SECONDS == 30.0


def test_an_answered_probe_holds_for_the_window_then_asks_again(clock, monkeypatch):
    gets: list[str] = []

    class Ok:
        def raise_for_status(self):
            return None

    monkeypatch.setattr(ollama_client.requests, "get", lambda url, **kw: gets.append(url) or Ok())
    runner = OllamaClient(BASE)
    assert runner.is_running()
    clock[0] += 29
    assert runner.is_running() and len(gets) == 1
    clock[0] += 1.5
    assert runner.is_running() and len(gets) == 2


def test_a_failed_request_drops_the_up_mark(clock):
    ollama_client.remember_up(BASE)
    assert ollama_client.recently_up(BASE)
    ollama_client._note_failure(BASE, TimeoutError("read"))
    assert not ollama_client.recently_up(BASE)


def test_seeing_ollama_online_drops_the_refused_and_silent_marks(clock):
    ollama_client._mark_down(BASE)
    ollama_client.mark_quiet(BASE)
    assert OllamaClient(BASE).is_running() is False
    ollama_client.note_online(BASE)
    assert not ollama_client._is_down(BASE) and not ollama_client.is_quiet(BASE)
    assert ollama_client.recently_up(BASE)
    assert OllamaClient(BASE).is_running() is True


def test_the_status_poll_calls_note_online_when_the_runner_answers():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "src/tessellate/api/routes_models.py").read_text(encoding="utf-8")
    assert "ollama_client.note_online(" in text
