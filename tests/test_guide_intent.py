"""The Guide reads what a question asks from its words before the tab it was
asked from (INBOX 904 B11, B86; BACKLOG "Guide answers what can I do in the
chat"). Each case was measured on the Graph tab with no model on 2026-10-17
and answered from the Graph's topic, the board library, the Ask and Chat
paragraph or Agent mode before this."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.ai import guide_intent, help_chat
from tessellate.entry import manager

ROOT = Path(__file__).resolve().parents[1]


def _guide(question: str, tab: str = "graph") -> dict:
    return help_chat.offline_answer(question, tab)


def test_how_to_use_the_app_is_the_overview_from_any_tab():
    for tab in ("graph", "reminders", None):
        said = _guide("How do I use the app??", tab)
        assert said["sources"][:1] == ["Tabs overview"], (tab, said["sources"])
        for name in ("Dashboard", "Notes", "Chat", "Graph", "Library", "Timeline", "Reminders"):
            assert f"**{name}**" in said["content"], (name, said["content"])
        assert "seven tabs" in said["content"]


def test_a_bare_request_for_help_says_what_the_guide_does_with_its_starters():
    for question in ("cna you help me", "can you help me?", "help", "I'm lost"):
        said = _guide(question)
        assert said.get("greeting") is True, (question, said)
        assert "Taking that as" not in said["content"] and "Graph" not in said["content"], said["content"]


def test_this_page_is_the_open_tabs_topic_not_a_topic_that_says_page():
    assert _guide("what is this page for", "graph")["sources"][:1] == ["Graph"]
    assert _guide("what does this tab do", "reminders")["sources"][:1] == ["Reminders"]
    assert _guide("what am I looking at")["sources"][:1] == ["Graph"]


@pytest.mark.parametrize(
    ("question", "tab", "where"),
    [
        ("what can I do in the chat?? like what should I ask for??", "graph", "chat"),
        ("what should I ask", "graph", "chat"),
        ("what should I ask", "notes", "notes"),
        ("what can I ask in the ask box", "graph", "notes"),
        ("give me some ideas", "reminders", "reminders"),
    ],
)
def test_asked_for_ideas_the_guide_gives_asks_for_that_surface(question, tab, where):
    said = _guide(question, tab)
    assert said["asks"] == list(guide_intent.ASKS[where]), said
    assert 3 <= len(said["asks"]) <= 5
    for ask in said["asks"]:
        assert f"- {ask}" in said["content"]
    assert said["asks_to"] == ("notes" if where == "notes" else "chat")


def test_what_atlas_can_change_is_the_act_registrys_list():
    said = _guide("What can Atlas change in my notebook?", "chat")
    text = said["content"]
    for words in ("set a reminder", "tag notes", "move notes to a category", "delete a note", "Undo", "confirm"):
        assert words in text, (words, text)
    assert "take a tag off" not in text and "Agent mode" not in text
    assert said["asks"] and said["asks_to"] == "chat"


def test_a_question_naming_a_feature_keeps_its_topic():
    """The readings stand aside for a question about a feature itself."""
    for question in ("how do I add a reminder", "how do I change the theme", "what is the graph for"):
        assert guide_intent.read(question) is None, question


def test_every_family_has_eight_phrasings_and_house_style():
    for family in (guide_intent._IDEAS_LEADS, guide_intent._HELP_LINES, guide_intent._ATLAS_LEADS):
        assert len(set(family)) >= 8
        for line in family:
            assert "!" not in line and chr(0x2014) not in line, line
    seen = {_guide(q)["content"].split("\n")[0] for q in ("what should I ask", "what can I ask?", "give me ideas", "what to ask",
                                                           "any suggestions", "what should we ask", "what could I try", "some examples")}
    assert len(seen) >= 3, seen


def _route(client, question: str, **body) -> str:
    text = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event.get("type") == "answer":
                    text.append(event["delta"])
    return "".join(text)


def test_every_ask_the_guide_offers_is_answered_with_no_model(client, session):
    """An offered ask that came back "nothing in your notes" would be the
    INBOX 304 fault again: a suggestion the app cannot answer."""
    for text in ("Golf practice after work, hit some balls", "Dentist on Tuesday at 3pm", "Read Atomic Habits chapter 3"):
        manager.create_entry(session, text)
    session.commit()
    for where, asks in guide_intent.ASKS.items():
        body = {"notes_only": True, "answer_from": "notes", "use_tools": False} if where == "notes" else {"use_tools": True}
        for ask in asks:
            said = _route(client, ask, **body).lower()
            assert said.strip(), (where, ask)
            for miss in ("nothing in your notes", "no mention", "couldn't find", "no note i found", "none of your notes"):
                assert miss not in said, (where, ask, said)


def test_the_guide_panel_renders_the_asks_as_chips():
    source = (ROOT / "frontend" / "js" / "help-chat.js").read_text(encoding="utf-8")
    assert "renderHelpChatAsks(answerRow, result.asks, result.asks_to)" in source
    assert "asks: done?.asks" in source
