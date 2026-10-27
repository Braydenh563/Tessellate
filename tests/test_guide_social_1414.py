"""INBOX 1414: the Guide's social and open questions (the owner: "composer
guide responses still need a lot of improvement and better intuition, intent
detection, social skills"). Behaviour, not strings: first person, one short
line for a greeting or thanks, no repeat after "that didn't help", a place
only when one was asked for, provenance not in the text (the chip says it),
a resume offer only for unfinished work, a follow-up that comes from the
question. No clock is read."""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer_aware, help_chat, reading  # noqa: F401  (reading sets the act reader hook)

#: The composed answers read preferences, which would make the repo data/ folder.
pytestmark = pytest.mark.usefixtures("app_state")

PINNED = ["Pinned a note"]
THIRD_PERSON = re.compile(r"\b(?:It answers|Atlas is this app|it still answers)\b")
HELP_DUMP = re.compile(r"\*\*(?:Where|Related):\*\*|\n1\. ")
PROVENANCE = re.compile(r"from the app'?s (?:own )?help|no model running", re.I)
RESUME = re.compile(r"part-way|pick up|carry on|where you left", re.I)

OPEN = [
    "what can you help me with",
    "who are you",
    "hi",
    "hello atlas",
    "thanks",
    "thank you that worked",
    "that didn't help",
    "you're wrong",
    "how do I organise this",
    "I'm lost",
    "can you book me a flight",
]
HOWTOS = [
    "how do I add a reminder",
    "where are my reminders",
    "what does web search do",
    "how do I tag a note",
    "how do I export my notes",
    "how do I change the theme",
]


def _reply(question: str, tab: str = "notes", actions=PINNED) -> str:
    out = help_chat._aware(help_chat.offline_answer(question, tab), question, tab, actions)
    return out["content"]


@pytest.mark.parametrize("question", OPEN + HOWTOS)
def test_no_reply_repeats_provenance_or_offers_a_resume_after_a_pin(question):
    text = _reply(question)
    assert not PROVENANCE.search(text), text
    assert not RESUME.search(text), text
    assert not THIRD_PERSON.search(text), text


@pytest.mark.parametrize("question", OPEN)
def test_an_open_question_gets_no_help_dump_and_no_place(question):
    assert not HELP_DUMP.search(_reply(question))


@pytest.mark.parametrize("question", ["what can you help me with", "who are you"])
def test_the_guide_speaks_of_itself_in_the_first_person(question):
    text = _reply(question)
    assert re.search(r"\bI(?: can|'m| answer)\b", text), text


@pytest.mark.parametrize("question", ["hi", "hello atlas", "thanks", "thank you that worked"])
def test_a_greeting_or_thanks_is_one_short_line(question):
    text = _reply(question)
    assert len(text.split()) <= 30 and "\n" not in text, text


def test_thanks_that_worked_is_not_answered_with_a_topic():
    assert help_chat.offline_answer("thank you that worked")["sources"] == []


@pytest.mark.parametrize("question", ["that didn't help", "you're wrong"])
def test_a_complaint_is_owned_and_asks_one_question(question):
    reply = help_chat.offline_answer(question, "notes")
    text = reply["content"]
    assert text.lower().startswith("sorry"), text
    assert text.count("?") == 1, text
    assert reply["sources"] == [] and not reply["badges"]


def test_a_vague_organise_asks_which_kind():
    text = _reply("how do I organise this")
    assert text.count("?") == 1 and "tags" in text, text


def test_a_request_beyond_the_app_says_so_in_the_first_person():
    text = _reply("can you book me a flight")
    assert text.startswith("I can't"), text
    assert "Capture a thought" not in text


def test_a_can_you_about_the_app_is_still_answered():
    text = _reply("can you set a reminder for me", actions=None)
    assert not text.startswith("I can't"), text


@pytest.mark.parametrize("question", HOWTOS)
def test_a_place_is_added_only_when_one_is_asked_for(question):
    text = help_chat.offline_answer(question, "notes")["content"]
    assert ("**Where:**" in text) <= bool(re.search(r"\b(?:where|find|locate)\b", question, re.I)), text


def test_a_resume_is_offered_for_an_open_note_not_for_a_finished_act():
    open_note = composer_aware.build(tab="notes", open_title="Trip plan", actions=PINNED)
    assert RESUME.search(composer_aware.closing(open_note, "s")) or "Trip plan" in composer_aware.closing(open_note, "s")
    pinned = composer_aware.build(tab="notes", actions=PINNED)
    assert not composer_aware.unfinished(pinned)
    assert not RESUME.search(composer_aware.closing(pinned, "s"))


def test_the_follow_up_comes_from_the_question_or_is_absent():
    off_topic = _reply("what does web search do")
    assert "tag a note" not in off_topic
    on_topic = _reply("what do the tabs do here", actions=PINNED)
    assert "how do I tag a note" in on_topic or "tag a note" not in on_topic
    asked = _reply("how do I tag a note")
    assert asked.count("how do I tag a note") == 0


# --- Follow-ups, 2026-10-27 (BACKLOG "Placed from the guide round").


@pytest.mark.parametrize("question", ["how do I pin a note", "how do I unpin a note", "pin a note"])
def test_pinning_a_note_is_answered_from_favourites_not_the_graph(question):
    # Pinning a note is starring it (app.js, `entry.pinned`); the Graph's
    # "pin a note" keyword used to answer it with the graph's node pin.
    ids = [t["id"] for t in help_chat.topics_for(question, "notes")]
    assert ids[0] in ("act-pin", "act-unpin", "favourites") and "graph-controls" not in ids, ids


def test_pinning_a_graph_node_still_finds_the_graphs_controls():
    assert "graph-controls" in [t["id"] for t in help_chat.topics_for("how do I pin a node in the graph", "graph")]


@pytest.mark.parametrize("question", ["who are you", "what can you do", "that didn't help", "hi", "thanks"])
def test_with_a_model_a_social_message_is_briefed_not_left_to_say_not_sure(question):
    messages, _ = help_chat._prompt_for(question, None, "notes", None)
    brief = [m["content"] for m in messages if m["role"] == "system" and "social" in m["content"]]
    assert len(brief) == 1 and help_chat.social_reply(question)["content"] in brief[0]


def test_a_question_about_the_app_carries_no_social_brief():
    messages, _ = help_chat._prompt_for("how do I add a reminder", None, "notes", None)
    assert not any("is social" in m["content"] for m in messages)


def test_chat_closes_with_the_same_closing_so_a_finished_act_is_not_resumed_there_either():
    # Decided 2026-10-27: a finished act ("Pinned a note") is no more
    # unfinished in Chat than in the Guide, so Chat keeps the 1414 rule.
    from pathlib import Path

    routes = (Path(__file__).resolve().parents[1] / "src/tessellate/api/routes_chat.py").read_text(encoding="utf-8")
    assert "composer_aware.closing(_awareness(req), seed, recent)" in routes
    pinned = composer_aware.build(tab="chat", actions=PINNED)
    assert not RESUME.search(composer_aware.closing(pinned, "chat-seed"))
