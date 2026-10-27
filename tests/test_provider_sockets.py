"""The tool-call paths over a real socket (WORLD_CLASS_PLAN row 19, CLAUDE.md
section 4).

Every other provider test fakes `requests`; these start the two stand-in
servers in `scratchpad/` on a free port and talk to them over TCP, so the
bytes are parsed the way a real server's would be: NDJSON lines for Ollama,
chunked SSE for the OpenAI dialect.

What they lift from the standing caveat: concurrent tool calls at index 1
(streamed interleaved, the hard order) and Ollama's native tool-call dialect,
both through the clients and through one whole agent turn, and the forced
round's `format` schema on Ollama with its fallback when refused. What they
cannot lift: whether a real model produces these shapes. The shapes are
written from each API's documentation and from the llama-server captures in
AGENT_SKILLS_REFORM H4; a real Ollama has not been run in this sandbox.
"""

from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

import pytest

from tessellate.ai.ollama_client import OllamaClient
from tessellate.ai.openai_client import OpenAICompatClient


@pytest.fixture(autouse=True)
def _scratch_data_dir(tmp_path, monkeypatch):
    """A request logs a job run under the data dir: a scratch one, never the repo's."""
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scratchpad" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ollama_server():
    module = _load("fake_ollama_server")
    server = module.serve(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield module, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture()
def openai_server():
    module = _load("fake_openai_server")
    server = module.serve(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield module, f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()
    server.server_close()


def _tool(name: str, **params) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {"type": "object", "properties": {k: {"type": v} for k, v in params.items()}},
        },
    }


TOOLS = [_tool("search_notes", query="string"), _tool("list_tags"), _tool("count_notes")]
ASK = [{"role": "user", "content": "search my notes and list my tags"}]


def _final(stream) -> dict:
    events = list(stream)
    return [e["final"] for e in events if "final" in e][0]


# --- the OpenAI dialect, two calls interleaved by index -------------------------------


def test_two_streamed_calls_interleaved_by_index_come_back_whole(openai_server, monkeypatch):
    module, url = openai_server
    monkeypatch.setattr(module, "CALLS", 2)
    final = _final(OpenAICompatClient(url, timeout=10).chat_tools_stream(module.MODEL_ID, ASK, TOOLS))
    assert [c["name"] for c in final["tool_calls"]] == ["list_tags", "search_notes"]
    assert final["tool_calls"][0]["arguments"] == {}
    # Index 1's JSON arrived in three-character pieces alternating with index
    # 0's: whole here means the fold went by index, not by arrival.
    assert final["tool_calls"][1]["arguments"] == {"query": "notes"}


def test_two_calls_unstreamed_too(openai_server, monkeypatch):
    module, url = openai_server
    monkeypatch.setattr(module, "CALLS", 2)
    out = OpenAICompatClient(url, timeout=10).chat_tools(module.MODEL_ID, ASK, TOOLS)
    assert [c["name"] for c in out["tool_calls"]] == ["list_tags", "search_notes"]
    assert out["tool_calls"][1]["arguments"] == {"query": "notes"}


# --- Ollama's native dialect -----------------------------------------------------------


def test_ollama_native_calls_arrive_as_objects_with_an_index(ollama_server, monkeypatch):
    module, url = ollama_server
    monkeypatch.setenv("FAKE_OLLAMA_CALLS", "2")
    final = _final(OllamaClient(url, timeout=10).chat_tools_stream("llama3.2:latest", ASK, TOOLS))
    assert [c["name"] for c in final["tool_calls"]] == ["list_tags", "search_notes"]
    assert final["tool_calls"][1]["arguments"] == {"query": "notes"}
    # Replayed back as Ollama's own shape on the next round.
    assert final["raw_tool_calls"][1]["function"]["index"] == 1


def test_ollama_native_unstreamed(ollama_server):
    _module, url = ollama_server
    out = OllamaClient(url, timeout=10).chat_tools("llama3.2:latest", ASK, TOOLS)
    assert [c["name"] for c in out["tool_calls"]] == ["list_tags"]


def test_ollama_forced_round_is_decoded_under_a_call_schema(ollama_server):
    """The grammar-forced first call: Ollama has no `tool_choice`, so the
    round carries a `format` schema, and the call comes back as JSON content
    that the client reads as the call and never shows."""
    module, url = ollama_server
    events = list(
        OllamaClient(url, timeout=10).chat_tools_stream("llama3.2:latest", ASK, TOOLS, tool_choice="required")
    )
    sent = module.REQUESTS[-1]
    assert sent["format"]["properties"]["name"]["enum"] == ["search_notes", "list_tags", "count_notes"]
    final = [e["final"] for e in events if "final" in e][0]
    assert [c["name"] for c in final["tool_calls"]] == ["list_tags"]
    assert not [e for e in events if e.get("content_delta")], "the call's JSON leaked into the answer"


def test_ollama_that_refuses_the_schema_gets_the_round_unforced(ollama_server, monkeypatch):
    module, url = ollama_server
    monkeypatch.setenv("FAKE_OLLAMA_REJECT_FORMAT", "1")
    final = _final(OllamaClient(url, timeout=10).chat_tools_stream("llama3.2:latest", ASK, TOOLS, tool_choice="required"))
    assert [c["name"] for c in final["tool_calls"]] == ["list_tags"]
    assert "format" in module.REQUESTS[-2] and "format" not in module.REQUESTS[-1]


def test_an_unforced_round_sends_no_format(ollama_server):
    module, url = ollama_server
    _final(OllamaClient(url, timeout=10).chat_tools_stream("llama3.2:latest", ASK, TOOLS))
    assert "format" not in module.REQUESTS[-1]


# --- one whole agent turn over the socket ---------------------------------------------


def test_an_agent_turn_runs_both_native_calls_and_answers(ollama_server, monkeypatch, ai_client):
    """A whole `/chat/stream` turn against the native dialect over TCP: both
    calls in the one reply are dispatched (neither parks the other), both
    results go back on the next round, and the turn ends in the server's
    words."""
    import json

    from tessellate.core import deps

    module, url = ollama_server
    monkeypatch.setenv("FAKE_OLLAMA_CALLS", "2")
    deps.override_ai(ollama=OllamaClient(url, timeout=10))
    with ai_client.stream("POST", "/chat/stream", json={"question": "search my notes and list my tags"}) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]
    ran = [e.get("name") or e.get("tool") for e in events if e.get("type") == "tool"]
    assert len(ran) == 2, events
    answer = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert module.ANSWER in answer
    second = module.REQUESTS[-1]["messages"]
    assert sum(1 for m in second if m.get("role") == "tool") == 2


def test_stopping_a_slow_stream_midway_stops_reading_at_once(openai_server, monkeypatch):
    """Ledger 1530: the stand-in answers in ~150 ms, too fast to press Stop in. With
    `STREAM_DELAY_MS` it takes eight pauses; closing the generator after the first
    piece must return long before the rest arrive, and the server must not stall."""
    import time

    module, url = openai_server
    monkeypatch.setattr(module, "STREAM_DELAY_MS", 300)
    stream = OpenAICompatClient(url, timeout=10).chat_stream(module.MODEL_ID, ASK)
    started = time.monotonic()
    first = next(piece for piece in stream if piece.get("content_delta"))
    stream.close()
    stopped_after = time.monotonic() - started
    assert first["content_delta"]
    # Eight pieces at 300 ms is 2.4 s; the first piece plus the close is well under half of it.
    assert stopped_after < 1.2, stopped_after
    # The server is still healthy for the next request.
    monkeypatch.setattr(module, "STREAM_DELAY_MS", 0)
    again = list(OpenAICompatClient(url, timeout=10).chat_stream(module.MODEL_ID, ASK))
    assert any(p.get("content_delta") for p in again)
