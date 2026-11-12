"""The harness reads what a small model meant (AGENT_SKILLS_REFORM, "Harness
robustness, 2026-10-04", INBOX 527).

Measured before (scratchpad/harness_argmeasure.py): 0 of 5 ordinary JSON
slips were read, each became `{}`; 11 of 31 tools with a required parameter
named the missing one; `get_note {"id": 1}` failed and `pin_note` read the
string "false" as true.
"""

from __future__ import annotations

import json

import pytest

from tessellate.ai import agent, tools
from tessellate.ai import fence
from tessellate.ai import agent_turn
from tessellate.ai.provider import loads_lenient, normalise_tool_calls


@pytest.mark.parametrize(
    "text",
    [
        '{"content": "milk",}',
        "{'content': 'milk'}",
        '{"content": "milk"',
        '```json\n{"content": "milk"}\n```',
        '{"content": "milk"} and then some words',
    ],
)
def test_ordinary_json_slips_are_read(text):
    assert loads_lenient(text)["content"] == "milk"


def test_python_literals_and_a_cut_off_string_are_read():
    assert loads_lenient('{"pinned": True, "note_id": 3}') == {"pinned": True, "note_id": 3}
    assert loads_lenient('{"content": "buy mi') == {"content": "buy mi"}


def test_valid_json_is_never_reinterpreted():
    assert loads_lenient('{"a": "it\'s, }"}') == {"a": "it's, }"}


def test_an_unreadable_call_is_marked_not_emptied():
    [call] = normalise_tool_calls([{"function": {"name": "create_note", "arguments": "content: milk"}}])
    assert call["arguments"] == {}
    assert call["invalid_arguments"] == "content: milk"
    [ok] = normalise_tool_calls([{"function": {"name": "create_note", "arguments": '{"content": "x",}'}}])
    assert ok == {"name": "create_note", "arguments": {"content": "x"}}


def test_a_missing_argument_is_named_with_an_example():
    _args, problem = tools.check_arguments("get_note", {})
    assert "note_id (integer)" in problem
    assert '"note_id": 12' in problem


def test_spellings_are_folded_to_the_schema():
    args, problem = tools.check_arguments("get_note", {"id": "7"})
    assert problem is None and args == {"note_id": 7}
    args, problem = tools.check_arguments("get_note", {"noteId": 7})
    assert problem is None and args["note_id"] == 7
    args, problem = tools.check_arguments("create_note", {"content": "x", "tag": "urgent"})
    assert problem is None and args["tags"] == ["urgent"]


def test_tags_reach_tag_note_s_add():
    args, problem = tools.check_arguments("tag_note", {"note_id": 1, "tags": ["urgent"]})
    assert problem is None and args == {"note_id": 1, "add": ["urgent"]}
    args, _ = tools.check_arguments("create_note", {"content": "x", "tags": ["a"]})
    assert args["tags"] == ["a"], "a tool that has `tags` keeps it"


def test_values_are_read_as_their_schema_types():
    args, problem = tools.check_arguments("pin_note", {"note_id": "#3", "pinned": "false"})
    assert problem is None and args == {"note_id": 3, "pinned": False}
    args, problem = tools.check_arguments("tag_note", {"note_id": 1, "add": "a, b"})
    assert args["add"] == ["a", "b"]
    args, problem = tools.check_arguments("set_reminder", {"text": "x", "due_at": "2026-10-05T09:00", "priority": "HIGH"})
    assert problem is None and args["priority"] == "high"


def test_an_unreadable_value_is_named():
    _args, problem = tools.check_arguments("get_note", {"note_id": "the plumber one"})
    assert "wrong type" in problem and "note_id (integer)" in problem


def test_execute_tool_refuses_before_the_handler(session):
    result = tools.execute_tool(session, "get_note", {})
    assert "note_id (integer)" in result["error"]


class _Session:
    def rollback(self):
        return None

    def commit(self):
        return None


class _Fake:
    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.sent: list[dict] = []

    def chat_tools_stream(self, model, messages, offered, mode=None):
        self.sent = list(messages)
        calls = self.rounds.pop(0) if self.rounds else []
        yield {"final": {"content": "" if calls else "done", "tool_calls": calls, "raw_tool_calls": []}}


class _Models:
    def chat_model(self):
        return "m"


def test_unreadable_json_comes_back_as_that_with_a_shape(monkeypatch, app_state):
    fake = _Fake([[{"name": "get_note", "arguments": {}, "invalid_arguments": "note_id=3"}], []])
    ran = []
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: ran.append(a) or {})
    events = list(agent.run_agent(_Session(), "q", [], _Models(), fake))
    assert not ran, "a call whose JSON did not read must not run with {}"
    payload = json.loads([m for m in fake.sent if m.get("role") == "tool"][-1]["content"])
    assert "not valid JSON" in payload["error"]
    assert '"note_id": 12' in payload["what_to_do"]
    assert any(e.get("type") == "tool" and e.get("ok") is False for e in events)


# --- running out of rounds ends in an answer ------------------------------------


class _Looping:
    """Calls a fresh search every round; with no tools offered, answers."""

    def __init__(self):
        self.offered: list[list] = []
        self.n = 0

    def chat_tools_stream(self, model, messages, offered, mode=None):
        self.offered.append(list(offered))
        if not offered:
            yield {"content_delta": "Your plumber note says the invoice is late."}
            yield {"final": {"content": "Your plumber note says the invoice is late.", "tool_calls": [], "streamed": True}}
            return
        self.n += 1
        call = {"name": "search_notes", "arguments": {"query": f"q{self.n}"}}
        yield {"final": {"content": "", "tool_calls": [call], "raw_tool_calls": []}}


def test_running_out_of_rounds_still_answers_from_what_was_found(monkeypatch, app_state):
    """Before: only "I stopped after N rounds". Now one more round with the
    tools withdrawn answers, and the stop and Continue still follow it."""
    fake = _Looping()
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"results": [], "label": "searched"})
    events = list(agent.run_agent(_Session(), "q", [], _Models(), fake, max_rounds=2, earned_rounds=0))
    answer = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert answer.startswith("Your plumber note says the invoice is late.")
    assert "Continue" in answer
    assert fake.offered[-1] == [], "the wrap-up round offers no tools"
    assert [e["type"] for e in events].index("limit") < len(events) - 1


def test_a_skill_step_that_runs_out_gets_no_wrap_up(monkeypatch, app_state):
    fake = _Looping()
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"results": []})
    events = list(
        agent.run_agent(_Session(), "q", [], _Models(), fake, max_rounds=2, earned_rounds=0, exhausted_note="stalled")
    )
    assert all(offered for offered in fake.offered)
    assert [e.get("delta") for e in events if e.get("type") == "answer"] == ["stalled"]


# --- the agent's own provider path retries a transient 5xx --------------------


def test_the_tools_stream_retries_a_503_once(openai_client, capture_post):
    """llama-server answers 503 while it loads a model. `chat` and
    `chat_stream` retried once; the agent's own path ended the turn."""
    from tests.fakes_http import FakeResponse, sse

    capture_post.queue.extend([
        FakeResponse(status=503, text="Loading model"),
        FakeResponse(lines=sse({"choices": [{"delta": {"content": "ok"}}]})),
    ])
    final = [p["final"] for p in openai_client.chat_tools_stream("m", [], []) if "final" in p][0]
    assert final["content"] == "ok"
    assert len(capture_post.sent) == 2
    assert "tools" not in capture_post.sent[0]["json"], "an empty tool list is not sent"


def test_a_second_5xx_is_still_an_error(openai_client, capture_post):
    from tests.fakes_http import FakeResponse

    from tessellate.ai.provider import ProviderError

    capture_post.queue.extend([FakeResponse(status=500), FakeResponse(status=500)])
    with pytest.raises(ProviderError):
        list(openai_client.chat_tools_stream("m", [], []))


# --- a result too big for what is left is shortened, not dropped ---------------


def _page(n=20, chars=500):
    return {
        "results": [{"id": i, "content": f"note {i} " + "x" * chars} for i in range(n)],
        "label": "searched",
    }


def test_a_result_that_fits_is_untouched():
    result = {"count": 3}
    assert json.loads(agent._fit_result(result, "count_notes", 1000)) == {"count": 3}


def test_a_big_page_is_shortened_from_the_back_with_a_note():
    """Measured: a 20-note page of 500-character notes is 11,166 characters
    fenced; the turn had 3,000 left. Before: dropped whole, tools withdrawn."""
    full = json.dumps(fence.fence_result(_page(), "search_notes"))
    payload = agent._fit_result(_page(), "search_notes", 3000)
    assert payload is not None and len(payload) <= 3000 < len(full)
    data = json.loads(payload)
    assert [row["id"] for row in data["results"]] == list(range(len(data["results"])))
    assert len(data["results"]) >= 3
    assert "Shortened to fit" in data["shortened"] and "left out" in data["shortened"]


def test_no_room_at_all_is_still_refused():
    assert agent._fit_result(_page(), "search_notes", 200) is None


# --- independent calls in one reply: none parked, web reads side by side -------


def test_two_searches_in_one_reply_both_run(monkeypatch, app_state):
    """Before: the first search marked the turn as having read outside text,
    so the second search in the same reply, chosen before anything was read,
    was parked behind a confirm card."""
    ran = []
    monkeypatch.setattr(agent.tools, "ollama_tools", lambda allowed=None: [])
    monkeypatch.setattr(agent.tools, "execute_tool", lambda s, n, a, **k: ran.append(n) or {"results": [], "label": n})
    monkeypatch.setattr(agent.tools, "prefetch_web", lambda calls: None)
    fake = _Fake([[
        {"name": "web_search", "arguments": {"query": "a"}},
        {"name": "web_search", "arguments": {"query": "b"}},
    ], [{"name": "read_url", "arguments": {"url": "https://x.example"}}], []])
    events = list(agent.run_agent(_Session(), "q", [], _Models(), fake))
    assert ran == ["web_search", "web_search"]
    assert [e["name"] for e in events if e.get("type") == "confirm"] == ["read_url"], (
        "a later round, chosen after reading outside text, still asks first"
    )


def test_three_pages_in_one_reply_are_fetched_side_by_side(monkeypatch, app_state, session):
    import time

    from tessellate.core import deps
    from tessellate.search import websearch

    deps.get_config().set_preference("web_search_enabled", True)
    fetched = []

    def slow(url):
        fetched.append(url)
        time.sleep(0.4)
        return {"url": url, "title": url, "text": "page text", "links": []}

    monkeypatch.setattr(websearch, "fetch_readable", slow)
    monkeypatch.setattr(agent.tools, "ollama_tools", lambda allowed=None: [])
    urls = [f"https://site{i}.example/" for i in range(3)]
    fake = _Fake([[{"name": "read_url", "arguments": {"url": u}} for u in urls], []])
    started = time.monotonic()
    events = list(agent.run_agent(session, "q", [], _Models(), fake))
    elapsed = time.monotonic() - started
    oks = [e for e in events if e.get("type") == "tool" and e.get("ok")]
    assert len(oks) == 3
    assert sorted(fetched) == urls, "each page fetched once, not again by the call"
    assert elapsed < 1.0, f"three 0.4s pages took {elapsed:.2f}s: fetched in series"


def test_no_match_is_not_said_to_be_an_empty_notebook():
    """Qwen2.5-1.5B, four notes saved: "How many notes do I have?" matched
    none by its words, the prompt said "My notebook looks empty", and the
    answer was "There are no notes in your notebook"."""
    prompt = agent_turn.build_agent_messages("How many notes do I have?", [])[-1]["content"]
    assert "looks empty" not in prompt
    assert "No notes matched" in prompt and "count_notes" in prompt


# --- reflect and retry: a claimed act is asked for once -------------------------


class _Claims:
    """Claims a note, then (asked) calls create_note, then says done."""

    def __init__(self, obey=True):
        self.obey = obey
        self.replies = 0
        self.sent: list[list[dict]] = []

    def chat_tools_stream(self, model, messages, offered, mode=None):
        self.sent.append(list(messages))
        self.replies += 1
        if self.replies == 2 and self.obey:
            call = {"name": "create_note", "arguments": {"content": "buy oat milk"}}
            yield {"final": {"content": "", "tool_calls": [call], "raw_tool_calls": []}}
            return
        text = "I've made a new note for you." if self.replies == 1 or not self.obey else "Saved."
        yield {"content_delta": text}
        yield {"final": {"content": text, "tool_calls": [], "streamed": True}}


def _offer(monkeypatch):
    monkeypatch.setattr(
        agent.tools, "ollama_tools", lambda allowed=None: [{"function": {"name": "create_note"}}]
    )


def test_a_claimed_note_is_asked_for_and_then_made(monkeypatch, app_state):
    _offer(monkeypatch)
    ran = []
    monkeypatch.setattr(agent.tools, "execute_tool", lambda s, n, a, **k: ran.append(n) or {"id": 5, "label": "made"})
    fake = _Claims()
    events = list(agent.run_agent(_Session(), "Make a note: buy oat milk", [], _Models(), fake))
    assert ran == [] and [e["name"] for e in events if e.get("type") == "confirm"] == ["create_note"]  # parked for consent (owner, 2026-11-10)
    nudge = fake.sent[1][-1]["content"]
    assert "saved a note" in nudge and "create_note" in nudge
    answer = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert "Heads up" not in answer


def test_a_second_false_claim_still_gets_the_heads_up(monkeypatch, app_state):
    _offer(monkeypatch)
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {})
    fake = _Claims(obey=False)
    events = list(agent.run_agent(_Session(), "Make a note: buy oat milk", [], _Models(), fake))
    answer = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert fake.replies == 2, "asked once, not twice"
    assert "Heads up: I said I saved a note" in answer


def test_adding_to_a_note_is_offered_the_edit():
    """Qwen2.5-1.5B, "Add 'bring a rain jacket' to my Snowdon trip note": no
    edit_note offered, so it rewrote the note in prose and saved nothing."""
    for question in (
        "Add 'bring a rain jacket' to my Snowdon trip note",
        "put the new address in my plumber note",
        "append this to the shopping note",
    ):
        assert "edit_note" in tools.focus_for(question), question
    assert "edit_note" not in tools.focus_for("Make a note: buy oat milk")


# --- a small model's imperative: the first round must be a call ----------------


class _SmallModels:
    def chat_model(self):
        return "qwen2.5:1.5b"

    def utility_model(self):
        return "qwen2.5:1.5b"


def _small_turn(monkeypatch, openai_client, capture_post, question):
    from tests.fakes_http import FakeResponse, sse

    capture_post.queue.extend([
        FakeResponse(lines=sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "a", "function": {"name": "create_note", "arguments": '{"content": "oat milk"}'}}
        ]}}]})),
        FakeResponse(lines=sse({"choices": [{"delta": {"content": "Saved."}}]})),
    ])
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"id": 1, "label": "made"})
    return list(agent.run_agent(_Session(), question, [], _SmallModels(), openai_client))


def test_an_imperative_on_a_small_model_requires_a_first_call(monkeypatch, app_state, openai_client, capture_post):
    """Measured on Qwen2.5-1.5B with llama.cpp: "Make a note: ..." got prose on
    most turns; with tool_choice "required" the server answered create_note."""
    _small_turn(monkeypatch, openai_client, capture_post, "Make a note: buy oat milk")
    sent = [request["json"] for request in capture_post.sent]
    assert sent[0].get("tool_choice") == "required"
    assert "tool_choice" not in sent[1], "only the first round"


def test_a_question_is_never_forced_into_a_call(monkeypatch, app_state, openai_client, capture_post):
    for question in ("How many notes do I have?", "can you pin it?", "What did I write about milk"):
        capture_post.sent.clear()
        _small_turn(monkeypatch, openai_client, capture_post, question)
        assert all("tool_choice" not in request["json"] for request in capture_post.sent), question
        capture_post.queue.clear()


def test_a_server_that_refuses_tool_choice_is_asked_again_without_it(openai_client, capture_post):
    from tests.fakes_http import FakeResponse, sse

    capture_post.queue.extend([
        FakeResponse(status=400, text="unknown field tool_choice"),
        FakeResponse(lines=sse({"choices": [{"delta": {"content": "ok"}}]})),
    ])
    offered = [{"type": "function", "function": {"name": "create_note", "parameters": {}}}]
    final = [p["final"] for p in openai_client.chat_tools_stream("m", [], offered, tool_choice="required") if "final" in p][0]
    assert final["content"] == "ok"
    assert "tool_choice" not in capture_post.sent[1]["json"]


# --- a forced round that comes back as prose (H4: the server's grammar did not hold)


def _prose(text):
    from tests.fakes_http import FakeResponse, sse

    return FakeResponse(lines=sse({"choices": [{"delta": {"content": text}}]}))


def _call(name, arguments):
    from tests.fakes_http import FakeResponse, sse

    return FakeResponse(lines=sse({"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": "a", "function": {"name": name, "arguments": arguments}}
    ]}}]}))


def test_a_forced_round_that_comes_back_as_prose_is_asked_once_more(monkeypatch, app_state, openai_client, capture_post):
    """Measured on Qwen2.5-3B (H4): one forced round answered in prose with
    `tool_choice: "required"` on the request. A reply that neither claims nor
    announces anything was the turn's answer; now it is asked once more, with
    the call required again, and the call it then makes is run."""
    capture_post.queue.extend([
        _prose("Oat milk and eggs, noted."),
        _call("create_note", '{"content": "buy oat milk and eggs"}'),
        _prose("Saved."),
    ])
    ran = []
    monkeypatch.setattr(agent.tools, "execute_tool", lambda s, n, a, **k: ran.append(n) or {"id": 1, "label": "made"})
    events = list(agent.run_agent(_Session(), "Make a note: buy oat milk and eggs", [], _SmallModels(), openai_client))
    sent = [request["json"] for request in capture_post.sent]
    assert ran == [] and [e["name"] for e in events if e.get("type") == "confirm"] == ["create_note"]  # parked for consent (owner, 2026-11-10)
    assert sent[0].get("tool_choice") == "required"
    assert sent[1].get("tool_choice") == "required", "the retry is forced again"
    assert "tool_choice" not in sent[2], "and only the retry"
    assert agent.FORCED_PROSE_NUDGE in [m.get("content") for m in sent[1]["messages"]]
    assert "Saved." in "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


def test_the_forced_re_prompt_is_made_once_not_in_a_loop(monkeypatch, app_state, openai_client, capture_post):
    capture_post.queue.extend([_prose("Noted."), _prose("Noted again."), _prose("Still prose.")])
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"id": 1})
    events = list(agent.run_agent(_Session(), "Make a note: buy oat milk", [], _SmallModels(), openai_client))
    assert len(capture_post.sent) == 2
    assert "Noted again." in "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


def test_a_large_model_is_not_re_prompted_for_prose(monkeypatch, app_state, openai_client, capture_post):
    class _Large:
        def chat_model(self):
            return "qwen3:14b"

        def utility_model(self):
            return "qwen3:14b"

    capture_post.queue.extend([_prose("Noted."), _prose("never asked")])
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"id": 1})
    list(agent.run_agent(_Session(), "Make a note: buy oat milk", [], _Large(), openai_client))
    assert len(capture_post.sent) == 1
