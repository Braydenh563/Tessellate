"""Several tool calls in one reply, at index 1 and beyond, in both dialects (L-world-class-69).

Fake transport: `requests.post` is replaced, so these pin the parsing and the loop, not a real model.
Real inference is unverified; the same shapes against a real model are the `evals` cases in
`tests/test_tool_calls_evals.py`.
"""

from __future__ import annotations

import json

import pytest

from tessellate.ai import agent
from tessellate.ai import ollama_client as oc
from tests.fakes_http import FakeResponse, sse

THREE = [
    ("count_notes", {}),
    ("search_notes", {"query": "boiler"}),
    ("get_note", {"note_id": 7}),
]


def _ollama_lines(calls, *, as_string=False, split=False):
    """Ollama's native stream: `message.tool_calls`, arguments an object (or a string some models send)."""
    wrapped = [
        {"function": {"name": n, "arguments": json.dumps(a) if as_string else a}} for n, a in calls
    ]
    if not split:
        chunks = [wrapped]
    else:
        chunks = [[w] for w in wrapped]
    lines = [json.dumps({"message": {"role": "assistant", "content": "", "tool_calls": c}, "done": False}) for c in chunks]
    lines.append(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}))
    return lines


def _openai_lines(calls, *, indexed=True):
    """OpenAI's stream: every call opens with an id and a name, arguments follow in pieces."""
    chunks = []
    for i, (name, args) in enumerate(calls):
        text = json.dumps(args)
        opener = {"id": f"c{i}", "function": {"name": name, "arguments": text[:3]}}
        rest = {"function": {"arguments": text[3:]}}
        if indexed:
            opener["index"], rest["index"] = i, i
        chunks.append((opener, rest))
    # Interleaved: all openers first, then all continuations, the way concurrent calls arrive.
    pieces = [{"choices": [{"delta": {"tool_calls": [o for o, _ in chunks]}}]}]
    pieces.append({"choices": [{"delta": {"tool_calls": [r for _, r in chunks]}}]})
    return sse(*pieces)


def _ollama(monkeypatch, bodies):
    sent: list = []

    def post(url, json=None, **kwargs):  # noqa: A002
        sent.append(json)
        if url.endswith("/api/show"):
            return FakeResponse(payload={})
        return bodies.pop(0) if bodies else FakeResponse(lines=_final_ollama())

    monkeypatch.setattr(oc.requests, "post", post)
    client = oc.OllamaClient("http://ollama.test")
    monkeypatch.setattr(client, "runtime_options", lambda model, mode=None: {})
    monkeypatch.setattr(client, "request_extras", lambda mode, model: {})
    monkeypatch.setattr(client, "_stats_from", lambda data, model: {})
    return client, sent


def _final_ollama():
    return [json.dumps({"message": {"role": "assistant", "content": "All three done."}, "done": True})]


def _final(client, messages=None):
    pieces = list(client.chat_tools_stream("m", messages or [{"role": "user", "content": "q"}], []))
    return [p["final"] for p in pieces if "final" in p][0]


@pytest.mark.parametrize("as_string", [False, True])
@pytest.mark.parametrize("split", [False, True])
def test_ollama_native_tool_calls_keep_every_call_in_order(monkeypatch, as_string, split):
    client, _ = _ollama(monkeypatch, [FakeResponse(lines=_ollama_lines(THREE, as_string=as_string, split=split))])
    final = _final(client)
    assert [c["name"] for c in final["tool_calls"]] == [n for n, _ in THREE]
    assert [c["arguments"] for c in final["tool_calls"]] == [a for _, a in THREE]
    assert len(final["raw_tool_calls"]) == 3


def test_openai_streamed_calls_at_index_two_and_beyond_are_reassembled(openai_client, capture_post):
    capture_post.queue.append(FakeResponse(lines=_openai_lines(THREE)))
    final = [p["final"] for p in openai_client.chat_tools_stream("m", [], []) if "final" in p][0]
    assert [(c["name"], c["arguments"]) for c in final["tool_calls"]] == THREE


def test_openai_calls_without_an_index_still_come_out_as_three(openai_client, capture_post):
    capture_post.queue.append(FakeResponse(lines=_openai_lines(THREE, indexed=False)))
    final = [p["final"] for p in openai_client.chat_tools_stream("m", [], []) if "final" in p][0]
    assert [c["name"] for c in final["tool_calls"]] == [n for n, _ in THREE]


def test_a_gap_in_the_indexes_and_a_nameless_bucket_lose_nothing_real(openai_client, capture_post):
    capture_post.queue.append(
        FakeResponse(
            lines=sse(
                {"choices": [{"delta": {"tool_calls": [
                    {"index": 2, "id": "c", "function": {"name": "get_note", "arguments": '{"note_id": 7}'}},
                    {"index": 5, "function": {"arguments": "{}"}},
                    {"index": 0, "id": "a", "function": {"name": "count_notes", "arguments": "{}"}},
                ]}}]},
            )
        )
    )
    final = [p["final"] for p in openai_client.chat_tools_stream("m", [], []) if "final" in p][0]
    assert [c["name"] for c in final["tool_calls"]] == ["count_notes", "get_note"]


class _Session:
    def rollback(self):
        return None

    def commit(self):
        return None


class _Models:
    def chat_model(self):
        return "m"


def _run_turn(monkeypatch, client):
    ran: list = []

    def execute(session, name, arguments, **kwargs):
        ran.append((name, arguments))
        return {"label": f"ran {name}", "echo": name}

    monkeypatch.setattr(agent.tools, "ollama_tools", lambda allowed=None: [])
    monkeypatch.setattr(agent.tools, "execute_tool", execute)
    sent: list = []
    real = client.chat_tools_stream

    def spy(model, messages, tools, **kwargs):
        sent.append(list(messages))
        return real(model, messages, tools, **kwargs)

    monkeypatch.setattr(client, "chat_tools_stream", spy)
    events = list(agent.run_agent(_Session(), "do three things", [], _Models(), client))
    return ran, sent, events


def _tool_replies(messages):
    return [json.loads(m["content"])["echo"] for m in messages if m.get("role") == "tool"]


def test_a_whole_ollama_turn_runs_every_call_and_returns_every_result(monkeypatch, app_state):
    client, _ = _ollama(monkeypatch, [FakeResponse(lines=_ollama_lines(THREE, split=True))])
    ran, sent, events = _run_turn(monkeypatch, client)
    assert [n for n, _ in ran] == [n for n, _ in THREE]
    assert ran[2][1] == {"note_id": 7}
    assert _tool_replies(sent[-1]) == [n for n, _ in THREE]
    assert any(e.get("type") == "answer" for e in events)


def test_a_whole_openai_turn_runs_every_call_and_returns_every_result(monkeypatch, app_state, openai_client, capture_post):
    capture_post.queue.append(FakeResponse(lines=_openai_lines(THREE)))
    capture_post.queue.append(FakeResponse(lines=sse({"choices": [{"delta": {"content": "All three done."}}]})))
    ran, sent, events = _run_turn(monkeypatch, openai_client)
    assert [n for n, _ in ran] == [n for n, _ in THREE]
    assert _tool_replies(sent[-1]) == [n for n, _ in THREE]
    assert any(e.get("type") == "answer" for e in events)
