"""Blind test 2026-10-31 (blind-1031.md, friction items 3 to 10): each test pins a class."""

from __future__ import annotations

import json

import pytest

from tessellate.ai import composer_digest
from tessellate.entry import manager


def _ask(client, question: str) -> dict:
    text, mode = "", None
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
        for line in response.iter_lines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event["type"] == "answer":
                text += event["delta"]
            elif event["type"] == "meta":
                mode = event.get("search_mode")
    return {"text": text, "mode": mode}


@pytest.fixture
def trip(session):
    manager.create_entry(session, "# Things to do\n\nOn the trip, see the castle and the tram.", category_name="Journal")
    manager.create_entry(session, "# Flight\n\nTP 303 from Gatwick at 7:45.", category_name="Journal")
    manager.create_entry(session, "# Hotel\n\nBooked near the river for three nights.", category_name="Journal")


@pytest.mark.parametrize("question", [
    "what do I know about my trip?",
    "What do I know about the trip?",
    "tell me about my trip",
])
def test_i3_a_words_only_search_never_claims_the_only_note(client, trip, question):
    got = _ask(client, question)
    assert got["mode"] == "keyword", got
    said = got["text"].lower()
    assert "only note" not in said and "just the one note" not in said, said
    assert "uses those words" in said, said


def test_i3_every_voice_of_the_only_note_line_is_known():
    lines = composer_digest.only_note_lines()
    assert "So far this is your only note on it." in lines
    assert "This is the only note on that." in lines
    assert all(isinstance(line, str) and line for line in lines)


def _function_body(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start:text.index("\n}\n", start)]


def test_i3_every_way_to_a_note_opens_it_out_and_focuses_it():
    """Item 3: "Open note" lands on the note itself (its row opened out, focus on
    it as a click leaves it), not the list with a two-second flash."""
    from tests._app_js import app_js_text

    body = _function_body(app_js_text(), "flashEntry")
    assert "expandedRows.add(id)" in body
    assert "card.focus(" in body
