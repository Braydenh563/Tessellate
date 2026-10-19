"""Needle is offered a shortlist, not the whole registry (owner log
2026-10-19: 72 tools, 30,089 chars, 50 s per call)."""
import json

import pytest

from tessellate.ai import needle_provider, tools

QUESTIONS = [
    "which of my notes mention deadlines in march",
    "tag my gardening notes and file them",
    "something with no cue words at all",
]


def _all() -> list[dict]:
    return [t["function"] for t in tools.ollama_tools(None)]


@pytest.mark.parametrize("question", QUESTIONS)
def test_a_typical_question_offers_under_fifteen_schemas(question):
    everything = _all()
    short = needle_provider.shortlist(everything, question)
    before, after = len(json.dumps(everything)), len(json.dumps(short))
    print("SCHEMAS", question, len(everything), "->", len(short), before, "->", after, "chars")
    assert 0 < len(short) <= needle_provider.NEEDLE_MAX_TOOLS
    assert after < before / 2


def test_a_small_set_is_left_alone():
    few = _all()[:5]
    assert needle_provider.shortlist(few, "anything") == few


def test_the_engine_receives_the_shortlist(monkeypatch):
    seen: list[list] = []

    class _Engine:
        def complete(self, system, tools_json, text):
            seen.append(json.loads(tools_json))
            return {"function_calls": []}

    provider = needle_provider.NeedleProvider()
    monkeypatch.setattr(provider, "_engine", lambda: _Engine())
    provider.chat_tools("needle", [{"role": "user", "content": QUESTIONS[0]}], tools.ollama_tools(None))
    assert len(seen[0]) <= needle_provider.NEEDLE_MAX_TOOLS
