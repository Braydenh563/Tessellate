"""CHAT_PLAN B6: the context window adapts to the model and the memory.

The owner: "why are the ai model context windows so small, can they be
larger?? they need to properly adapt to the model." A fixed 8192 ceiling put a
128k model on a 5k budget. Fake transports only: nothing here has run a real
model, so the memory cost of a window is the estimate from /api/show's shape.
"""

from __future__ import annotations

import pytest

from tessellate.ai import context, librarian
from tessellate.ai.ollama_client import OllamaClient
from tessellate.ai.openai_client import OpenAICompatClient
from tessellate.core import hardware

# 32 layers x 8 KV heads x 128 wide x 2 (K and V) x 2 bytes = 131,072 B/token.
KV_PER_TOKEN = 2 * 32 * 8 * 128 * 2


class _Prefs:
    def __init__(self, **values):
        self.values = values

    def get_preference(self, key, default=None):
        return self.values.get(key, default)


@pytest.fixture
def prefs(monkeypatch):
    import tessellate.core.deps as deps

    def use(**values):
        monkeypatch.setattr(deps, "get_config", lambda: _Prefs(**values))

    use()
    return use


@pytest.fixture
def memory(monkeypatch):
    def use(free_gb, vram_gb=None):
        monkeypatch.setattr(hardware, "free_memory_gb", lambda: free_gb)
        monkeypatch.setattr(
            hardware, "detect_gpus", lambda: [{"name": "g", "vram_gb": vram_gb}] if vram_gb else []
        )

    return use


def ollama_model(context_length, shape=True):
    client = OllamaClient(base_url="http://127.0.0.1:1")
    info = {"llama.context_length": context_length}
    if shape:
        info.update(
            {
                "llama.block_count": 32,
                "llama.attention.head_count": 32,
                "llama.attention.head_count_kv": 8,
                "llama.embedding_length": 4096,
            }
        )
    client._shown = {"m": {"model_info": info}}
    return client


def test_the_cache_cost_is_read_from_the_model_shape(prefs):
    assert ollama_model(131072).kv_bytes_per_token("m") == KV_PER_TOKEN
    assert ollama_model(131072, shape=False).kv_bytes_per_token("m") is None


# model length, free GB, expected window (KV share is 40% of free memory)
CASES = [
    (4096, 64, 4096),
    (4096, 8, 4096),
    (32768, 64, 32768),
    (32768, 8, 25600),  # 3.2 GiB / 128 KiB = 26,214 -> 25,600
    (131072, 64, 131072),
    (131072, 8, 25600),
    (131072, 16, 52224),  # 6.4 GiB / 128 KiB = 52,428 -> 52,224
]


@pytest.mark.parametrize(("length", "free", "expected"), CASES)
def test_window_follows_model_and_memory(prefs, memory, length, free, expected):
    memory(free)
    client = ollama_model(length)
    assert client.usable_context("m") == expected
    # What is asked of the backend is what is budgeted against.
    assert client.runtime_options("m")["num_ctx"] == expected
    # The librarian's budget and the agent's (agent_turn plans from the same
    # usable_context) scale from it.
    assert librarian.plan_budget("m", client).window_tokens == expected
    assert context.plan(client.usable_context("m"), 2000).window_tokens == expected


def test_a_128k_model_gets_a_bigger_budget_than_the_old_cap(prefs, memory):
    memory(64)
    big = context.plan(ollama_model(131072).usable_context("m"), 2000)
    old = context.plan(OllamaClient.MAX_REQUESTED_CONTEXT, 2000)
    assert big.notes_chars > 10 * old.notes_chars
    assert big.fits


def test_video_memory_counts_when_it_is_larger(prefs, memory):
    memory(4, vram_gb=24)
    assert ollama_model(131072).usable_context("m") == 77824  # 9.6 GiB / 128 KiB = 78,643


def test_never_below_the_default_floor(prefs, memory):
    memory(0.5)
    assert ollama_model(131072).usable_context("m") == OllamaClient.DEFAULT_CONTEXT_TOKENS


def test_no_shape_or_unreadable_memory_keeps_the_old_cap(prefs, memory):
    memory(64)
    assert ollama_model(131072, shape=False).usable_context("m") == 8192
    memory(None)
    assert ollama_model(131072).usable_context("m") == 8192


def test_the_global_preference_still_wins(prefs, memory):
    memory(64)
    prefs(max_context_tokens=16384)
    client = ollama_model(131072)
    assert client.usable_context("m") == 16384
    assert "ceiling in preferences" in client.context_explanation("m")


def test_a_hand_set_window_wins_over_everything(prefs, memory):
    memory(8)
    prefs(model_context_windows={"m": 65536}, max_context_tokens=16384)
    client = ollama_model(131072)
    assert client.usable_context("m") == 65536
    assert client.context_explanation("m") == "Set by you: 65,536 tokens."


def test_settings_sentence_says_why(prefs, memory):
    memory(8)
    spec = ollama_model(131072).model_spec("m")
    assert spec["usable_context"] == 25600
    assert "free memory" in spec["context_reason"]
    assert "\u2014" not in spec["context_reason"]
    memory(64)
    assert "full window" in ollama_model(131072).model_spec("m")["context_reason"]


@pytest.mark.parametrize("n_ctx", [4096, 32768, 131072])
def test_llama_server_budgets_to_the_reported_window(prefs, memory, n_ctx):
    """llama-server fixes the window at load: there is nothing to allocate, so
    the reported n_ctx is used as it stands, with no memory cap on top."""
    memory(1)
    client = OpenAICompatClient(base_url="http://localhost:8080/v1")
    client._catalog = []
    client._props = {"n_ctx": n_ctx}
    assert client.usable_context("m") == n_ctx
    assert librarian.plan_budget("m", client).window_tokens == n_ctx
    assert "server sets it" in client.context_explanation("m")


def test_an_openai_server_that_only_guesses_keeps_the_cap(prefs, memory):
    client = OpenAICompatClient(base_url="http://localhost:1234/v1")
    client._context_lengths = {"m": 131072}
    assert client.usable_context("m") == OpenAICompatClient.MAX_REQUESTED_CONTEXT


def test_an_unreadable_per_model_preference_logs_its_own_name(monkeypatch, caplog):
    """Review of PR 216: the except branch of `preferred_context` said
    "max_context_tokens unreadable" while reading `model_context_windows`."""
    import logging

    import tessellate.core.deps as deps

    def broken():
        raise RuntimeError("preferences file gone")

    monkeypatch.setattr(deps, "get_config", broken)
    with caplog.at_level(logging.INFO, logger="tessellate.provider"):
        assert ollama_model(8192).preferred_context("m") is None
    assert "model_context_windows unreadable" in caplog.text
    assert "max_context_tokens" not in caplog.text


def test_the_memory_window_is_decided_once_per_model(prefs, memory):
    """Review of PR 216: `num_ctx` is the window, and Ollama reloads a model
    when `num_ctx` changes, so free memory read afresh on every turn (it drops
    the moment the model loads) moved the window by a 1,024 step and reloaded
    the model each time. One decision per model for the life of the client."""
    memory(8)
    client = ollama_model(131072)
    client._shown["m2"] = client._shown["m"]
    first = client.usable_context("m")
    assert first == 25600
    memory(64)  # more memory freed up: no growth mid-session
    assert client.usable_context("m") == first
    memory(2)  # the loaded model took its share: no shrink either
    assert client.usable_context("m") == first
    assert client.runtime_options("m")["num_ctx"] == first
    assert "free memory" in client.context_explanation("m")
    # Another model is its own decision; a new client (a new session) reads memory again.
    memory(16)
    assert client.usable_context("m2") == 52224
    assert ollama_model(131072).usable_context("m") == 52224
