"""Agent mode with no model (INBOX 801).

The owner, 2026-10-11, six screenshots: "It said waking a model when no model
is connected" / "Cant do basic utility" / "it doesnt account for accidental
extra characters like a backslash" / "it doesnt output tool results with the
composer". Each screenshot is a case here, through the real `/chat/stream`
with no model configured, both without the Needle extra and with it installed
(a fake engine, as `test_needle_provider.py` holds it): the engine answers
what it can read, Needle never shadows it, and what Needle does run is said as
an answer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tessellate.ai import arithmetic, needle_provider, question_noise, utilities
from tessellate.entry import manager
from tests.test_needle_provider import TOOLS, _install_fake_needle

ROOT = Path(__file__).resolve().parents[1]


def _ask(client, question: str, **body) -> dict:
    events: dict[str, list] = {}
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["type"], []).append(event)
    events["text"] = "".join(e["delta"] for e in events.get("answer", []))
    return events


def _seed(session) -> None:
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.")
    manager.create_entry(session, "# Harbor launch\n\nShip the app on the 14th.")
    session.commit()


@pytest.fixture(autouse=True)
def _scratch_data_dir(tmp_path, monkeypatch):
    """The needle provider's tests log under the data dir: a scratch one, never the repo's."""
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))


@pytest.fixture(params=["engine only", "needle installed"])
def no_model(request, client, session, monkeypatch, app_state):
    """`client` has no model running; the second run also has Needle on disk,
    with an engine that records every call it is asked to make."""
    asked: list[str] = []
    if request.param == "needle installed":
        needle_provider.reset_for_tests()
        _install_fake_needle()

        class _Engine:
            def complete(self, system, tools_json, text):
                asked.append(text)
                return {"function_calls": []}

        monkeypatch.setattr(needle_provider, "_get_engine", lambda: _Engine())
    _seed(session)
    yield client, asked
    needle_provider.reset_for_tests()


def test_the_time_in_a_named_place(no_model):
    client, asked = no_model
    out = _ask(client, "what's the time in western australia")
    assert re.match(r"It's \d\d:\d\d(?: on \w+ \d+ \w+ \d{4})? in Perth, Western Australia \(AWST, UTC\+8\)\.", out["text"])
    assert "Read as Australia/Perth, from this computer's clock." in out["text"]
    assert "None of my tools" not in out["text"] and asked == []


def test_a_bare_sum(no_model):
    client, asked = no_model
    out = _ask(client, "5 + 5")
    assert out["text"] == "5 + 5 is 10."
    assert asked == []


def test_notebook_stats_in_capitals_counts_and_searches_nothing(no_model):
    client, asked = no_model
    out = _ask(client, "NOTEBOOK STATS")
    assert out["text"].startswith("You have 2 notes")
    assert not out.get("tool") and asked == []


def test_what_is_there_about_a_topic_with_a_stray_backslash(no_model):
    client, asked = no_model
    out = _ask(client, "what is there about dentist\\")
    #: Said as a digest (decision 70): the fact, then where it came from.
    assert "Check-up booked for the 21st" in out["text"] and "night guard" in out["text"]
    assert "\\" not in out["text"] and asked == []


def test_can_you_search_the_web_with_web_off(no_model):
    client, asked = no_model
    out = _ask(client, "can you search the web?")
    #: Decision 65's wording: whether, how, and the switch's state.
    assert out["text"].startswith("Yes, when web search is on.") and "It is off now" in out["text"]
    assert not out.get("tool") and asked == []
    assert out["meta"][0]["composed"] is False


def test_no_answer_says_a_step_holds_the_result(no_model):
    client, _asked = no_model
    for question in ("what's the time in western australia", "5 + 5", "NOTEBOOK STATS"):
        text = _ask(client, question)["text"]
        assert "result is in the step above" not in text and "Couldn't ask" not in text


# --- the pieces --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "meant"),
    [
        ("what is there about dentist\\", "what is there about dentist"),
        ("NOTEBOOK STATS", "notebook stats"),
        ("5  +   5", "5 + 5"),
        ("\\notebook stats", "notebook stats"),
        ("NASA", "NASA"),
        ("ok :\\", "ok :\\"),
        ("first line\n\nsecond  line|", "first line\n\nsecond line"),
    ],
)
def test_a_question_is_tidied_before_anything_reads_it(typed, meant):
    assert question_noise.tidy(typed) == meant


@pytest.mark.parametrize(("typed", "expr"), [("5 + 5", "5 + 5"), ("5+5=", "5+5"), ("3 x 4", "3 x 4"), ("12 - 3", "12 - 3")])
def test_a_bare_sum_is_read(typed, expr):
    assert arithmetic.sum_in(typed) == expr


@pytest.mark.parametrize("typed", ["2024-10-11", "10/11", "7", "the 5 notes"])
def test_a_date_or_a_number_is_not_a_sum(typed):
    assert arithmetic.sum_in(typed) is None


@pytest.mark.parametrize(
    ("place", "zone"),
    [("western australia", "Australia/Perth"), ("Tokyo", "Asia/Tokyo"), ("new york", "America/New_York"),
     ("WA", "Australia/Perth"), ("Europe/Paris", "Europe/Paris"), ("my notes", None)],
)
def test_a_place_is_read_as_its_zone(place, zone):
    assert utilities.zone_for(place) == zone


def test_the_time_tool_takes_a_place(session, app_state):
    from tessellate.ai import tools

    there = tools.execute_tool(session, "get_current_time", {"place": "Tokyo"})
    assert there["zone"] == "Asia/Tokyo" and there["iso"].endswith("+09:00")
    assert "error" in tools.execute_tool(session, "get_current_time", {"place": "Narnia"})


# --- what Needle is offered, what it is given, and how its results are said ----------------


def _offered(fake) -> list[str]:
    return [t["name"] for t in json.loads(fake.inits[-1][1])]


class _Lib:
    def __init__(self, answers):
        self.answers = list(answers)
        self.tools: list[str] = []

    def complete(self, system, tools_json, text):
        self.tools = [t["name"] for t in json.loads(tools_json)]
        return self.answers.pop(0) if self.answers else {"function_calls": []}


ASK_AND_SEARCH = TOOLS + [
    {"type": "function", "function": {"name": "ask_user", "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
    {"type": "function", "function": {"name": "search_notes", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]


def test_ask_user_is_never_offered_to_needle(monkeypatch):
    lib = _Lib([{"function_calls": [{"name": "ask_user", "arguments": {"question": "which?"}}]}])
    monkeypatch.setattr(needle_provider, "_get_engine", lambda: lib)
    reply = needle_provider.NeedleProvider().chat_tools("any", [{"role": "user", "content": "x"}], ASK_AND_SEARCH)
    assert "ask_user" not in lib.tools and "search_notes" in lib.tools
    assert reply["tool_calls"] == []


def test_an_empty_search_gets_the_cleaned_topic(monkeypatch):
    lib = _Lib([{"function_calls": [{"name": "search_notes", "arguments": {"query": ""}}]}])
    monkeypatch.setattr(needle_provider, "_get_engine", lambda: lib)
    reply = needle_provider.NeedleProvider().chat_tools(
        "any", [{"role": "user", "content": "what is there about the dentist\\"}], ASK_AND_SEARCH
    )
    assert reply["raw_tool_calls"][0]["function"]["arguments"] == {"query": "dentist"}


def test_a_search_with_no_topic_is_not_run(monkeypatch):
    lib = _Lib([{"function_calls": [{"name": "search_notes", "arguments": {}}]}])
    monkeypatch.setattr(needle_provider, "_get_engine", lambda: lib)
    reply = needle_provider.NeedleProvider().chat_tools("any", [{"role": "user", "content": "search?"}], ASK_AND_SEARCH)
    assert reply["tool_calls"] == []


def test_found_notes_are_said_as_the_answer():
    result = {
        "found": 1,
        "notes": [{"id": 1, "content": "# Dentist\n\nCheck-up booked for the 21st."}],
        "label": "ph:magnifying-glass Searched notes for “dentist”",
    }
    messages = [{"role": "user", "content": "x"}, {"role": "tool", "tool_name": "search_notes", "content": json.dumps(result)}]
    reply = needle_provider.NeedleProvider().chat_tools("any", messages, TOOLS)
    #: Said by `tool_say` (the owner, 2026-10-11): each note linked, with
    #: its first line, and the next tap.
    assert reply["content"] == "I found one note about “dentist”.\n\n- [Dentist](#/notes/1): Check-up booked for the 21st.\n\n[Open it](#/notes/1)"


def test_the_time_and_a_sum_are_said_as_the_answer():
    messages = [
        {"role": "user", "content": "x"},
        {"role": "tool", "tool_name": "get_current_time", "content": json.dumps({"human": "Sunday 11 October 2026, 11:45", "place": "Perth"})},
        {"role": "tool", "tool_name": "calculate", "content": json.dumps({"answer": "5 + 5 is 10.", "read_as": "5 + 5"})},
    ]
    reply = needle_provider.NeedleProvider().chat_tools("any", messages, TOOLS)
    assert reply["content"] == "It is Sunday 11 October 2026, 11:45 in Perth.\n\n5 + 5 is 10."


def test_an_unsaid_result_is_said_by_its_label_and_an_error_by_its_reason():
    messages = [
        {"role": "user", "content": "x"},
        {"role": "tool", "tool_name": "pin_note", "content": json.dumps({"ok": True, "label": "ph:push-pin Pinned “Dentist”"})},
        {"role": "tool", "tool_name": "tag_note", "content": json.dumps({"error": "No note has that id."})},
    ]
    reply = needle_provider.NeedleProvider().chat_tools("any", messages, TOOLS)
    assert reply["content"] == (
        "Pinned “Dentist”.\n\nI could not find that note.\n\n"
        "It may have been deleted, or the number is wrong. Look for it in Notes.\n\n[Open Notes](#/notes)"
    )


def test_the_route_asks_needle_only_when_the_engine_has_no_answer():
    source = (ROOT / "src" / "tessellate" / "api" / "routes_chat.py").read_text(encoding="utf-8")
    helper = source[source.index("def _tools_provider(") : source.index("def _stream_lines(")]
    assert "not _engine_answers(req, prepared)" in helper


# --- INBOX 808, the owner's real log, with a model ------------------------------------------


def _model_events(client, question):
    out = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
        for line in response.iter_lines():
            if line.strip():
                out.append(json.loads(line))
    return out


def test_a_one_option_ask_is_stopped_and_never_loops(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "a note about beans"})
    one = [{"name": "ask_user", "arguments": {"question": "Shall I?", "options": ["yes"]}}]
    fake_ollama.tool_script = [one, [{"name": "ask_user", "arguments": {"question": "Shall I now?", "options": ["yes", "yes"]}}]]
    fake_ollama.librarian_reply = "Here is what your notes say about beans."
    events = _model_events(ai_client, "have a look")
    assert not [e for e in events if e["type"] in ("tool", "ask")], "no Couldn't ask step, no one-choice card"
    assert "beans" in "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    told = [m for m in fake_ollama.tool_rounds[-1] if m.get("role") == "tool"]
    assert len(told) == 2 and all("only one option" in m["content"] for m in told)


def test_a_search_with_no_query_is_given_the_requests_topic(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "# Gaming mouse\n\nThe one with side buttons."})
    fake_ollama.tool_script = [[{"name": "search_notes", "arguments": {"query": ""}}]]
    events = _model_events(ai_client, "what is there about a gaming mouse?\\")
    searched = [e for e in events if e["type"] == "tool" and e.get("tool") == "search_notes"]
    assert searched and searched[0]["arguments"]["query"] == "gaming mouse"


def test_a_tool_argument_loses_its_stray_backslash(ai_client, fake_ollama):
    fake_ollama.tool_script = [[{"name": "search_notes", "arguments": {"query": "a gaming mouse?\\"}}]]
    events = _model_events(ai_client, "find my mouse notes")
    searched = [e for e in events if e["type"] == "tool" and e.get("tool") == "search_notes"]
    assert searched and searched[0]["arguments"]["query"] == "a gaming mouse?"


def test_can_you_search_the_web_is_answered_plainly_with_a_model(ai_client, fake_ollama):
    fake_ollama.tool_script = [[{"name": "search_notes", "arguments": {"query": "none"}}]]
    events = _model_events(ai_client, "can you search the web?")
    text = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    #: Decision 75: with a model up the model answers, and nothing searches.
    assert text and not [e for e in events if e["type"] == "tool"]


def test_with_web_on_it_says_how_to_ask(ai_client, fake_ollama, app_state):
    app_state.set_preference("web_search_enabled", True)
    events = _model_events(ai_client, "can you search the web?")
    text = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    #: Decision 75: the model answers; the capability line is its context
    #: (tests/test_composer_social.py reads the prompt).
    assert text and not [e for e in events if e["type"] == "tool"]


@pytest.mark.parametrize(("typed", "topic"), [("what is there about a gaming mouse?\\", "gaming mouse"), ("search", ""),
                                             ("My notes:\n1. x\n\nMy request: notes about the dentist", "dentist")])
def test_the_topic_of_a_request(typed, topic):
    assert question_noise.topic_of(typed) == topic
