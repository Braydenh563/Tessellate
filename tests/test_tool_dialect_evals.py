"""Concurrent tool calls at index 1 and beyond, and Ollama's native tool-call dialect
(LEDGER L-world-class-69, CLAUDE.md section 4).

Two halves, one scoring helper:

* The fake-transport half runs in every suite. It drives the two stand-in servers in
  `scratchpad/` (the same ones `test_provider_sockets.py` uses) through `whole_calls`, so the
  helper the real-model half scores with cannot pass an empty or torn reply.
* The `evals` half asks a real model, as `test_harness_evals.py` does (TESSELLATE_EVALS_URL and
  TESSELLATE_EVALS_MODEL; skipped without them, so the module always collects). What is
  asserted is what the client guarantees whatever the model says: every call that comes back is
  whole (an offered name, arguments that parse to an object), and calls past index 0 are kept.
  How often a model asks for two calls in one reply is printed for the plan, never asserted.
  Run with `-s` to read the numbers. Real Ollama is only used when the URL answers `/api/tags`.
"""

from __future__ import annotations

import importlib.util
import os
import threading
from pathlib import Path

import pytest

from tessellate.ai.ollama_client import OllamaClient
from tessellate.ai.openai_client import OpenAICompatClient

ROOT = Path(__file__).resolve().parents[1]
EVALS_URL = os.environ.get("TESSELLATE_EVALS_URL", "").strip()
EVALS_MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "").strip()
needs_a_model = pytest.mark.skipif(
    not (EVALS_URL and EVALS_MODEL),
    reason="no real model: export TESSELLATE_EVALS_URL and TESSELLATE_EVALS_MODEL",
)


def _tool(name: str, **params) -> dict:
    props = {k: {"type": v} for k, v in params.items()}
    return {"type": "function", "function": {"name": name, "description": name, "parameters": {"type": "object", "properties": props}}}


TOOLS = [_tool("search_notes", query="string"), _tool("list_tags"), _tool("count_notes")]
NAMES = {t["function"]["name"] for t in TOOLS}

#: Asks that want two tools in one reply.
TWO_AT_ONCE = [
    "Search my notes for the plumber and also list my tags",
    "How many notes do I have, and what tags am I using?",
    "Look up the dentist in my notes and tell me how many notes there are",
]


def whole_calls(calls: list[dict]) -> bool:
    """Every call is an offered tool with arguments that are an object: none torn across fragments."""
    return all(c.get("name") in NAMES and isinstance(c.get("arguments"), dict) for c in calls)


def _final(stream) -> dict:
    return [e["final"] for e in stream if "final" in e][0]


def _serve(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scratchpad" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return module, server


@pytest.fixture(autouse=True)
def _scratch_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))


def test_the_helper_refuses_a_torn_or_unknown_call():
    assert whole_calls([{"name": "list_tags", "arguments": {}}, {"name": "search_notes", "arguments": {"query": "x"}}])
    assert not whole_calls([{"name": "list_tags", "arguments": "{\"qu"}])
    assert not whole_calls([{"name": "delete_everything", "arguments": {}}])


def test_openai_index_one_arrives_whole_over_the_socket(monkeypatch):
    module, server = _serve("fake_openai_server")
    try:
        monkeypatch.setattr(module, "CALLS", 2)
        url = f"http://127.0.0.1:{server.server_address[1]}/v1"
        calls = _final(OpenAICompatClient(url, timeout=10).chat_tools_stream(module.MODEL_ID, [{"role": "user", "content": TWO_AT_ONCE[0]}], TOOLS))["tool_calls"]
    finally:
        server.shutdown()
        server.server_close()
    assert len(calls) == 2 and whole_calls(calls)


def test_ollama_native_index_one_arrives_whole_over_the_socket(monkeypatch):
    module, server = _serve("fake_ollama_server")
    try:
        monkeypatch.setenv("FAKE_OLLAMA_CALLS", "2")
        url = f"http://127.0.0.1:{server.server_address[1]}"
        final = _final(OllamaClient(url, timeout=10).chat_tools_stream("llama3.2:latest", [{"role": "user", "content": TWO_AT_ONCE[0]}], TOOLS))
    finally:
        server.shutdown()
        server.server_close()
    assert len(final["tool_calls"]) == 2 and whole_calls(final["tool_calls"])
    assert final["raw_tool_calls"][1]["function"]["index"] == 1


def _ask_all(client, model: str) -> tuple[int, int, int]:
    """(replies, replies with two or more calls, calls that were not whole) over `TWO_AT_ONCE`."""
    many = torn = 0
    for ask in TWO_AT_ONCE:
        calls = _final(client.chat_tools_stream(model, [{"role": "user", "content": ask}], TOOLS))["tool_calls"]
        many += len(calls) >= 2
        torn += sum(not whole_calls([c]) for c in calls)
    return len(TWO_AT_ONCE), many, torn


@pytest.mark.evals
@needs_a_model
def test_a_real_model_s_concurrent_calls_come_back_whole_through_the_openai_dialect():
    replies, many, torn = _ask_all(OpenAICompatClient(base_url=EVALS_URL, timeout=120), EVALS_MODEL)
    print(f"\nCONCURRENT CALLS {EVALS_MODEL.rsplit('/', 1)[-1]}: {many}/{replies} replies held two or more calls; {torn} torn")
    assert torn == 0, "a call past index 0 came back torn or under an unoffered name"


@pytest.mark.evals
@needs_a_model
def test_a_real_ollama_s_native_calls_come_back_whole():
    client = OllamaClient(EVALS_URL, timeout=120)
    if not client.is_running():
        pytest.skip("TESSELLATE_EVALS_URL does not answer Ollama's /api/tags: the native dialect needs a real Ollama")
    replies, many, torn = _ask_all(client, EVALS_MODEL)
    print(f"\nNATIVE CALLS {EVALS_MODEL}: {many}/{replies} replies held two or more calls; {torn} torn")
    assert torn == 0, "a native call past index 0 came back torn or under an unoffered name"
