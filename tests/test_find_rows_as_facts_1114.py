"""L-chat-239: the rows of a search act ("find my gym notes") are carried as facts to the model, which words
them under the figure check, as a list or a count is (`tests/test_model_writes_facts_1027.py`). With no model the
engine's own line stands; a reply that miscounts the rows is refused for the engine's."""

from __future__ import annotations

import json

import pytest

from tessellate.core.database import Entry


def _seed(session) -> None:
    for text in ("# Gym plan\n\nLegs on Monday, back on Thursday.", "# Gym bag\n\nTowel, shoes, water bottle.", "# Boiler\n\nPressure is low."):
        session.add(Entry(content=text))
    session.commit()


def _stream(client, question: str, use_tools: bool = False) -> tuple[list, str]:
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": use_tools}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events, "".join(e.get("delta", "") for e in events if e["type"] == "answer")


def _prompt(fake) -> str:
    return "\n".join(str(m.get("content") or "") for m in fake.chat_calls[-1])


@pytest.mark.parametrize("question", ["find my gym notes", "find notes about gym"])
def test_the_found_rows_go_to_the_model_as_facts(ai_client, fake_ollama, session, question):
    _seed(session)
    fake_ollama.librarian_reply = "Two notes match: Gym plan and Gym bag."
    events, answer = _stream(ai_client, question)
    assert fake_ollama.chat_calls, "the model was never asked"
    prompt = _prompt(fake_ollama)
    assert "Gym plan" in prompt and "Gym bag" in prompt and "Boiler" not in prompt, prompt
    assert answer.startswith(fake_ollama.librarian_reply), answer
    assert [e for e in events if e["type"] == "meta"][-1]["answered_by"], events


def test_a_reply_that_miscounts_the_rows_is_refused_for_the_engines_own(ai_client, fake_ollama, session):
    _seed(session)
    fake_ollama.librarian_reply = "Five notes match: Gym plan and Gym bag."
    events, answer = _stream(ai_client, "find my gym notes")
    assert "Five notes" not in answer and "Gym plan" in answer and "Gym bag" in answer, answer
    assert [e for e in events if e["type"] == "meta"][-1]["answered_by"] is None


def test_with_no_model_the_engines_line_stands(client, session):
    _seed(session)
    _events, answer = _stream(client, "find my gym notes")
    assert "Gym plan" in answer and "Gym bag" in answer, answer
