"""L241 (audit P27): a 20-turn chat with a name saved, no model.

The rules, as the code states them (`ai/address.py` docstring; the audit text that numbered them is not in the repo):

- rule 4, where the name never goes: not in a fact answer, a list, a card or an error;
- rule 5, how often it is said: on the first hello of a chat once, and never again on the turns after.

Asking for it ("what's my name") is the one answer that says it every time it is asked.
"""

from __future__ import annotations

import json

from tessellate.core import deps

NAME = "Zephyrine"

#: A fixed conversation: a hello, then every kind of answer the composer gives.
TURNS = (
    "good morning", "what notes do I have", "list my notes", "how many notes do I have", "what is on my reminders",
    "what did I save about plans", "hello again", "hi", "summarise my notes", "what is two plus two",
    "show me my recent notes", "how do I record a meeting", "what is the airspeed of a swallow", "thanks", "what can you do",
    "list my tags", "what is due this week", "good evening", "which notes are about money", "frobnicate the zeitgeist",
)


def _ask(client, question: str, history: list[dict]) -> str:
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "history": history, "answer_from": "notes", "use_tools": False}) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e["delta"] for e in events if e["type"] == "answer")


def test_the_name_is_said_on_the_first_hello_at_most_once_and_never_after(client):
    assert len(TURNS) == 20
    deps.get_config().set_preference("display_name", NAME)
    history: list[dict] = []
    said = []
    for question in TURNS:
        answer = _ask(client, question, history)
        said.append(NAME in answer)
        history.append({"question": question, "answer": answer})
    assert sum(said) <= 1, [t for t, s in zip(TURNS, said) if s]
    assert not any(said[1:]), [t for t, s in zip(TURNS[1:], said[1:]) if s]


def test_asking_for_the_name_says_it_every_time(client):
    deps.get_config().set_preference("display_name", NAME)
    history: list[dict] = []
    for question in ("good morning", "what's my name", "what notes do I have", "who am I"):
        answer = _ask(client, question, history)
        history.append({"question": question, "answer": answer})
        if "name" in question or "who" in question:
            assert NAME in answer, question
