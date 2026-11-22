"""Composer audit 2, G7 and "Name use" (1110): the composer answers the name
questions, takes "call me Sam" behind Confirm, and uses the name sparingly.
Parity: the model-on path reads the same sentences."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest

from tessellate.ai import address
from tessellate.core import deps


def _ask(client, question: str, **body) -> dict:
    events: dict[str, list] = {}
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["type"], []).append(event)
    events["text"] = "".join(e["delta"] for e in events.get("answer", []))
    return events


def _name(value: str) -> None:
    deps.get_config().set_preference("display_name", value)


NAME_QUESTIONS = ("what's my name", "what is my name", "do you know my name", "what do you call me", "who am I", "what am I called")


@pytest.mark.parametrize("question", NAME_QUESTIONS)
def test_every_name_question_is_answered_from_the_profile(client, question):
    _name("Alex")
    out = _ask(client, question)
    assert "Alex" in out["text"] and "going by your profile" in out["text"], out["text"]


def test_no_name_saved_says_so_and_points_to_settings(client):
    _name("")
    text = _ask(client, "what's my name")["text"]
    assert "don't know" in text and "Settings" in text


@pytest.mark.parametrize("question", ("call me Sam", "my name is Sam", "you can call me Sam", "please call me sam"))
def test_call_me_is_a_card_and_saves_nothing_until_confirmed(client, question):
    _name("Alex")
    out = _ask(client, question)
    cards = out.get("act", [])
    assert cards and "Sam" in cards[0]["label"], out
    assert deps.get_config().get_preference("display_name", "") == "Alex"
    run = client.post("/chat/command/run", json={"steps": cards[0]["steps"]})
    assert run.status_code == 200, run.text
    assert deps.get_config().get_preference("display_name", "") == "Sam"
    undo = run.json()["undo"]
    assert undo
    client.post("/chat/command/run", json={"steps": [s for s in undo]})
    assert deps.get_config().get_preference("display_name", "") == "Alex"


@pytest.mark.parametrize("text", ("call me later", "call me back tomorrow", "call me when you get this", "call me at 5", "call mum"))
def test_call_me_something_else_is_not_a_name(text):
    assert address.read_set(text) is None


def test_the_model_path_reads_the_same_sentence(session):
    from tessellate.ai import act_registry, acts

    assert acts.parse("call me Sam", datetime(2026, 11, 10, 9, 0))["intent"] == "set_name"
    assert "set_name" in act_registry.ACTS and act_registry.ACT_TOOLS["set_name"] == "set_display_name"
    assert act_registry.ACTS["set_name"].confirm


def test_a_model_running_answers_the_name_question_the_same(ai_client, fake_ollama):
    _name("Alex")
    out = _ask(ai_client, "what's my name")
    assert "You're Alex, going by your profile." in out["text"]


def test_dashboard_name_is_decided_by_the_server():
    address._LAST.update(day=None, named=False)
    day = date(2026, 11, 10)
    assert address.dashboard_append("Alex", ".", day, "morning") is True
    assert address.dashboard_append("Alex", "?", day, "afternoon") is False
    flags = [address.dashboard_append("Alex", ".", day + timedelta(days=d), f"h{h}") for d in range(7) for h in range(24)]
    assert sum(flags) <= 0.4 * len(flags)
    assert not any(a and b for a, b, hour in zip(flags, flags[1:], range(1, len(flags))) if hour % 24)
    assert address.dashboard_append("", ".", day, "x") is True  # no name saved: nothing is added either way


def test_the_greeting_route_sends_the_flag(client):
    _name("Alex")
    body = client.get("/insights/greeting?block=morning").json()
    assert body["append_name"] is True
    flags = [client.get(f"/insights/greeting?block={b}").json()["append_name"] for b in ("afternoon", "evening", "morning", "afternoon")]
    assert not all(flags)


def test_the_first_hello_of_a_chat_takes_the_name_once():
    assert address.greet("Good morning. Ready when you are.", "Alex", []) == "Good morning, Alex. Ready when you are."
    assert address.greet("Good morning.", "Alex", [{"answer": "hi"}]) == "Good morning."
    assert address.greet("Good morning.", "", []) == "Good morning."


def test_the_name_is_cut_at_forty_characters():
    assert len(address.clean("A" * 80)) <= address.CUT


def test_a_welcome_with_a_comma_after_the_greeting_takes_the_name():
    """L-chat-114 (C12): "Good afternoon, and welcome back." was left nameless."""
    assert address.greet("Good afternoon, and welcome back. Nothing is due.", "Sam", []) == "Good afternoon, Sam, and welcome back. Nothing is due."


@pytest.mark.parametrize(("voice", "named"), [("natural", True), ("professional", False)])
def test_the_first_hello_names_you_unless_the_voice_is_professional(client, voice, named):
    _name("Sam")
    deps.get_config().set_preference("composer_voice", voice)
    said = _ask(client, "hello")["text"]
    assert ("Sam" in said.split(".")[0]) is named, said
