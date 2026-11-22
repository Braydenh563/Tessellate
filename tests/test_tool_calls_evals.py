"""Several tool calls in one reply, against a real model (L-world-class-69). Skipped without one.

Two dialects: the OpenAI-compatible stream (`TESSELLATE_EVALS_URL`, set by the dev runner) and Ollama's
native `message.tool_calls` (`TESSELLATE_EVALS_OLLAMA_URL`, a running Ollama). The fake-transport
twins are in `tests/test_tool_calls_index_69.py`; these ask whether a small model produces the shape
at all, and the rate over ten tries is what BACKLOG records.
"""

from __future__ import annotations

import os

import pytest

URL = os.environ.get("TESSELLATE_EVALS_URL", "").strip()
OLLAMA_URL = os.environ.get("TESSELLATE_EVALS_OLLAMA_URL", "").strip()
MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "").strip()
TRIES = 10

ASK = (
    "In one reply, call all three tools at once: count_notes, search_notes with the query boiler, "
    "and get_note with note_id 7. Do not wait for any result."
)
TOOLS = [
    {"type": "function", "function": {"name": name, "description": text, "parameters": {"type": "object", "properties": props}}}
    for name, text, props in (
        ("count_notes", "Count the notes.", {}),
        ("search_notes", "Search the notes.", {"query": {"type": "string"}}),
        ("get_note", "Read one note.", {"note_id": {"type": "integer"}}),
    )
]
OFFERED = {"count_notes", "search_notes", "get_note"}


def _rate(client) -> tuple[int, int]:
    """(replies with two or more calls, replies whose calls were all offered tools with readable arguments)."""
    several = well_formed = 0
    for _ in range(TRIES):
        pieces = client.chat_tools_stream(MODEL, [{"role": "user", "content": ASK}], TOOLS)
        calls = [p["final"] for p in pieces if "final" in p][0]["tool_calls"]
        several += len(calls) >= 2
        well_formed += len(calls) >= 2 and all(c["name"] in OFFERED and not c.get("invalid_arguments") for c in calls)
    return several, well_formed


@pytest.mark.evals
@pytest.mark.skipif(not (URL and MODEL), reason="no real model: set TESSELLATE_EVALS_URL and TESSELLATE_EVALS_MODEL")
def test_a_real_model_calls_several_tools_in_one_openai_reply(tmp_path, monkeypatch):
    from tessellate.ai.openai_client import OpenAICompatClient

    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    several, well_formed = _rate(OpenAICompatClient(base_url=URL))
    print(f"openai dialect: {several}/{TRIES} replies with 2+ calls, {well_formed}/{TRIES} well formed")
    assert well_formed >= 1, "no reply carried a second well-formed call at index 1 or beyond"


@pytest.mark.evals
@pytest.mark.skipif(not (OLLAMA_URL and MODEL), reason="no Ollama: set TESSELLATE_EVALS_OLLAMA_URL and TESSELLATE_EVALS_MODEL")
def test_a_real_model_calls_several_tools_in_one_native_ollama_reply(tmp_path, monkeypatch):
    from tessellate.ai.ollama_client import OllamaClient

    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    several, well_formed = _rate(OllamaClient(OLLAMA_URL))
    print(f"ollama native dialect: {several}/{TRIES} replies with 2+ calls, {well_formed}/{TRIES} well formed")
    assert well_formed >= 1, "no reply carried a second well-formed call at index 1 or beyond"
