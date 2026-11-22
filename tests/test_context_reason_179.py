"""L-chat-179 (the owner, 2026-10-10: "why is the token window limit for this model soooo low"): every turn's
stats say why the window is the size it is, and the pill's popover shows that sentence."""

from __future__ import annotations

from tests.test_adaptive_context_b6 import ollama_model, memory, prefs  # noqa: F401
from tests._app_js import frontend_text
from pathlib import Path


def test_the_stats_of_a_turn_carry_the_reason_for_the_window(prefs, memory):  # noqa: F811
    memory(1)
    client = ollama_model(131072)
    stats = client._stats_from({"prompt_eval_count": 10, "eval_count": 5}, "m")
    assert stats["context_tokens"] == client.usable_context("m")
    assert stats["context_reason"] == client.context_explanation("m")
    assert "free memory" in stats["context_reason"], stats["context_reason"]


def test_the_popover_shows_the_reason_and_the_real_figure():
    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="chat-context-pop-why"' in html
    ledger = frontend_text("usage-ledger.js")
    assert 'stats.context_reason' in ledger and "chat-context-pop-why" in ledger
