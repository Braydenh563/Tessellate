"""Audit 1028 E35, E36, E39 and E40."""

from __future__ import annotations

from tests._app_js import app_js_text
from tessellate.ai import model_manager
from tessellate.ai.model_manager import Job
from tessellate.ai.ollama_client import OllamaClient


def test_a_finished_chat_answer_is_said_once_to_a_screen_reader():
    """E35: the transcript is not a live region; the finished answer is announced."""
    js = app_js_text()
    assert 'if (endState === "done" && viewing()) announce(timeline.text());' in js


def test_a_saved_chat_opens_from_the_keyboard():
    """E36."""
    js = app_js_text()
    row = js[js.index('title.className = "conv-title";'):][:700]
    assert "title.tabIndex = 0;" in row and 'setAttribute("role", "button")' in row
    assert 'event.key !== "Enter" && event.key !== " "' in row and "openConversation(conversation.id)" in row


def test_the_not_working_toast_waits_while_the_download_question_is_up():
    """E40: one toast, not two saying the same thing."""
    assert "!installing && !modelStatus.semantic_offer && embeddingToastDue()" in app_js_text()


class _Pulling(OllamaClient):
    def __init__(self, base_url, lines):
        super().__init__(base_url)
        self.lines = lines

    def pull(self, name):  # noqa: ANN001
        yield from self.lines


def test_a_pull_that_cannot_fit_stops_with_the_space_to_free(monkeypatch):
    """E39: a layer larger than the free space fails before it fills the disk."""
    monkeypatch.setattr(model_manager.diskspace, "free_bytes", lambda path: 2 * 1024**3)
    job = Job(kind="pull", name="big")
    client = _Pulling("http://localhost:11434", [{"status": "pulling", "total": 5 * 1024**3, "completed": 0}])
    model_manager._run_pull(client, "big", job)
    assert job.status == "error" and "Not enough free space: free up 3.0 GB" in job.error


def test_a_remote_ollama_disk_is_not_checked(monkeypatch):
    monkeypatch.setattr(model_manager.diskspace, "free_bytes", lambda path: 0)
    job = Job(kind="pull", name="big")
    client = _Pulling("http://10.0.0.5:11434", [{"status": "pulling", "total": 5 * 1024**3, "completed": 0}])
    model_manager._run_pull(client, "big", job)
    assert job.status == "success"


def test_a_silent_download_connection_times_out(monkeypatch):
    """E39: no total timeout, but a five-minute silence ends it."""
    import requests

    from tessellate.ai import ollama_client

    seen = {}

    def fake_post(url, json=None, stream=False, timeout=None):  # noqa: ANN001, A002
        seen["timeout"] = timeout
        raise requests.ConnectionError("dead")

    monkeypatch.setattr(ollama_client.requests, "post", fake_post)
    client = OllamaClient("http://localhost:11434")
    try:
        list(client.pull("x"))
    except Exception:  # noqa: BLE001, S110
        pass
    assert seen["timeout"] == (10, 300)
