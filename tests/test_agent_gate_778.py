"""INBOX 778, the owner: "well the agent mode was still an option when I was
on the chat with no ai running". `ollama_running` only says a server answered;
Agent mode is gated on `model_ready`, which says a model can write a reply."""

from __future__ import annotations

from pathlib import Path

from tessellate.core import deps


def _status(client) -> dict:
    return client.get("/models/status").json()


def test_server_down_is_not_ready(client):
    body = _status(client)
    assert body["ollama_running"] is False and body["model_ready"] is False


def test_server_up_with_nothing_installed_is_not_ready(ai_client, fake_ollama):
    fake_ollama.installed = []
    body = _status(ai_client)
    assert body["ollama_running"] is True and body["model_ready"] is False


def test_ollama_up_without_the_chosen_model_is_not_ready(ai_client, fake_ollama):
    fake_ollama.installed = [{"name": "other:1b", "size": 1}]
    body = _status(ai_client)
    assert body["chat_model_installed"] is False and body["model_ready"] is False


def test_ollama_up_with_the_chosen_model_is_ready(ai_client):
    body = _status(ai_client)
    assert body["chat_model_installed"] is True and body["model_ready"] is True


def test_openai_server_answers_with_whatever_it_has_loaded(ai_client, fake_ollama):
    # llama.cpp / LM Studio ignore the requested name, so any listed model counts.
    deps.get_config().set_preference("llm_provider", "openai")
    fake_ollama.installed = [{"name": "gemma-4-E4B", "size": 1}]
    body = _status(ai_client)
    assert body["provider"] == "openai" and body["model_ready"] is True
    fake_ollama.installed = []
    assert _status(ai_client)["model_ready"] is False


def test_the_chat_mode_gate_reads_model_ready_not_reachability():
    """The gate's inputs: `model_ready`, or Needle. A null status (before the
    first poll, or a failed one) is neither, so Agent starts greyed."""
    status_js = Path("frontend/js/status.js").read_text(encoding="utf-8")
    gate = status_js.split("function agentModeAvailable() {", 1)[1].split("}", 1)[0]
    assert "modelStatus?.model_ready === true" in gate and "modelStatus?.tools_engine" in gate
    assert "aiIsOff" not in gate and "ollama_running" not in gate


def test_ai_is_off_when_no_model_can_answer_not_only_when_the_server_is_down():
    """Ledger 1521: `aiIsOff` follows `model_ready`, with the Needle engine keeping the gate open."""
    from tests._app_js import app_js_text

    code = app_js_text()
    body = code[code.index("function aiIsOff("):]
    body = body[: body.index("\n}\n")]
    assert "ollama_running === false" in body
    assert "model_ready === false" in body and "tools_engine" in body


def test_server_up_with_no_model_still_reports_the_tools_engine(ai_client, fake_ollama, monkeypatch):
    """L166: Agent greyed when the server was up but no model was installed, though Needle could run it."""
    from tessellate.api import routes_models

    monkeypatch.setattr(routes_models, "_tools_engine", lambda: "needle")
    fake_ollama.installed = []
    body = _status(ai_client)
    assert body["ollama_running"] is True and body["model_ready"] is False and body["tools_engine"] == "needle"
    fake_ollama.installed = [{"name": body["chat_model"] or "x", "size": 1}]
    assert _status(ai_client)["tools_engine"] is None
