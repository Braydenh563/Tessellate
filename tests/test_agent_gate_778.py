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
    """Ledger 1521, L643: the verdict is the server's one `ai_off` field (the
    runner down, or no model ready and no Needle engine), and `aiIsOff` reads
    only that, so 28 call sites cannot drift from a copied predicate. The
    predicate moved server-side, so this asserts the reader, not its clauses."""
    from tests._app_js import app_js_text

    code = app_js_text()
    body = code[code.index("function aiIsOff() {"):]
    body = body[: body.index("\n}\n")]
    assert "ai_off === true" in body
    assert "model_ready" not in body and "ollama_running" not in body and "tools_engine" not in body


def test_ai_off_when_the_runner_is_down_needle_or_not(client, monkeypatch):
    """L643: down is off first, as `ollama_running === false` was in the page."""
    from tessellate.api import routes_models

    assert _status(client)["ai_off"] is True
    monkeypatch.setattr(routes_models, "_tools_engine", lambda: "needle")
    assert _status(client)["ai_off"] is True


def test_ai_off_follows_whether_a_model_can_answer(ai_client, fake_ollama):
    assert _status(ai_client)["ai_off"] is False  # the chosen model is there
    fake_ollama.installed = []
    assert _status(ai_client)["ai_off"] is True  # up, nothing to answer with
