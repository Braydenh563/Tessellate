"""The Guide with no model (INBOX 787, the owner: "the atlas guide repeted
twice?? and it ist customised with the composer yet either. I feel like if
the user is set to view the deterministic response, they should have the
option to see either the base help text or a slightly more customised
version with the composer").

A greeting is answered as a greeting, never with the open tab's topic; a
topic answer says each sentence once; the default answer is composed for the
question (its lead sentence, where the feature lives, the steps), and the
help text word for word is the other side of the answer's toggle.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import pytest

from tessellate.ai import help_chat, reading

#: Importing `reading` wires the Guide's reader and the composer's help line.
READER_LOADED = reading.__name__
# The composer registers the help line; reading sets the act reader ("how do i pin a note").
importlib.import_module("tessellate.ai.composer")
importlib.import_module("tessellate.ai.reading")
JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _sentences(text: str) -> list[str]:
    flat = re.sub(r"[#*]", "", text)
    return [s.strip() for s in re.split(r"(?<=[.?])\s+|\n+", flat) if len(s.split()) >= 4]


@pytest.mark.parametrize("hello", ["hey", "Hi", "hello there", "hey atlas", "good morning"])
def test_a_greeting_is_answered_as_one_not_with_the_tabs_topic(hello):
    reply = help_chat.offline_answer(hello, tab="dashboard")
    assert reply.get("greeting") is True
    assert help_chat.GUIDE_NAME in reply["content"]
    assert "Dashboard" not in reply["content"] and not reply["badges"] and not reply["sources"]
    assert help_chat.topics_for(hello, "dashboard") == []


def test_thanks_gets_a_short_reply():
    reply = help_chat.offline_answer("thanks", tab="graph")
    assert reply["content"] == help_chat.THANKS_REPLY and not reply["badges"]


@pytest.mark.parametrize(
    "question",
    ["how do I set a reminder?", "where is backup", "how do I export my notes", "what does the dashboard show",
     "how do I change the theme", "how do I scan a document"],
)
def test_a_topic_answer_says_each_sentence_once(question):
    content = help_chat.offline_answer(question)["content"]
    said = _sentences(content)
    assert len(said) == len(set(said)), content


def test_the_provenance_line_reads_naturally():
    assert "word for word: no model" not in help_chat.OFFLINE_LEAD
    assert help_chat.OFFLINE_LEAD == "From the app's help, with no model running."


def test_the_default_answer_is_composed_and_the_help_text_is_the_other_view():
    question = "how do I set a reminder?"
    reply = help_chat.offline_answer(question)
    topic = help_chat.topics_for(question)[0]
    #: The help text word for word is the toggle's other side.
    assert topic["body"] in reply["system"]["content"]
    assert reply["system"]["content"] not in reply["content"]
    #: The composed side is shorter than the whole topic and names where it is.
    assert len(reply["content"]) < len(reply["system"]["content"])
    assert "Reminders tab" in reply["content"]
    assert reply["content"].rstrip().endswith(help_chat.OFFLINE_LEAD)


def test_a_topic_with_steps_gives_its_steps():
    reply = help_chat.offline_answer("how do I capture a note")
    assert "1. Open the Notes tab" in reply["content"]


def test_a_where_question_leads_with_the_place():
    reply = help_chat.offline_answer("where do I find the logs")
    assert reply["content"].startswith("It's in Settings, Logs.")


def test_a_how_to_lead_answers_the_verb_asked():
    """"How do I make a reminder" led with how the tab is laid out (Overdue,
    Today, Upcoming, Done); the sentence that says how to make one leads."""
    content = help_chat.offline_answer("how do I make a reminder")["content"]
    first = content.split("\n", 1)[0]
    assert "Overdue / Today" not in first, first


def test_the_route_sends_both_views(client):
    body = client.post("/help/ask", json={"question": "how do I set a reminder?"}).json()
    assert body["system"]["content"] and body["system"]["content"] not in body["content"]
    hey = client.post("/help/ask", json={"question": "hey", "tab": "dashboard"}).json()
    assert hey["greeting"] is True and not hey["badges"]


def test_the_client_draws_the_starters_under_a_greeting():
    js = (JS / "help-chat.js").read_text(encoding="utf-8")
    assert "result?.greeting" in js
    assert "atlasStartersFor(" in js[js.index("function renderHelpChatGreeting") :]


def test_the_guide_topic_says_what_the_two_views_are():
    guide = next(t for t in help_chat.HELP_TOPICS if t["id"] == "guide")
    assert "From the help" in guide["body"]


# The Guide's gold questions (fixtures/composer/guide_1011.json): first topic right and first line answering, switch topics, sentence ends

GOLD = json.loads((Path(__file__).parent / "fixtures" / "composer" / "guide_1011.json").read_text(encoding="utf-8"))["questions"]
FLOOR = 1.0


def _lead(question: str) -> str:
    paras = help_chat.offline_answer(question)["content"].split("\n\n")
    return next(p for p in paras if not p.startswith(("My reading", "Reading that", "I read that"))).lower()


def test_the_gold_questions_reach_their_topic():
    wrong = [(q, help_chat.topics_for(help_chat._read_as(q)[0])[0]["id"]) for q, ids, _w in GOLD
             if help_chat.topics_for(help_chat._read_as(q)[0])[0]["id"] not in ids]
    assert len(GOLD) >= 25 and 1 - len(wrong) / len(GOLD) >= FLOOR, wrong


def test_the_gold_questions_are_answered_in_the_first_line(app_state):
    wrong = [(q, _lead(q)[:120]) for q, _ids, words in GOLD if not any(w in _lead(q) for w in words)]
    assert 1 - len(wrong) / len(GOLD) >= FLOOR, wrong


@pytest.mark.parametrize(
    ("body", "want"),
    [
        ("Skills are requests above the chat box (e.g. \"Summarise my week\"). Add your own in Settings, Skills today.",
         ["Skills are requests above the chat box (e.g. \"Summarise my week\").", "Add your own in Settings, Skills today."]),
        ("Plays them at 0.5x or 2x speed in the player. Add to calendar (.ics) saves a file you can open.",
         ["Plays them at 0.5x or 2x speed in the player.", "Add to calendar (.ics) saves a file you can open."]),
        ("Manage categories (a category's ... menu) renames and merges them. Notes keys and controls.",
         ["Manage categories (a category's ... menu) renames and merges them."]),
    ],
)
def test_a_help_sentence_ends_where_a_sentence_ends(body, want):
    assert help_chat.help_sentences(body) == want


def test_a_switch_topic_says_how_the_switch_is_set_now(monkeypatch):
    for on in (False, True):
        monkeypatch.setattr(help_chat, "_preference", lambda _key, _default, on=on: on)
        lead = help_chat.offline_answer("how do i turn on web search")["content"].split("\n\n")[0]
        assert lead.startswith(f"Web search is {'on' if on else 'off'} now. Turn it on in Settings, Web search"), lead
        assert "by default" not in lead


def test_a_privacy_question_is_answered_yes_or_no_first():
    assert _lead("is my data sent anywhere").startswith("no. your notes stay on this computer")
    assert _lead("where did my deleted notes go").startswith("it's in the bin")


def test_how_to_use_the_app_in_chat_is_the_guide_s_even_with_a_note_word():
    """The Chromium after-run, 2026-10-11: in Chat "how do i export everything
    to markdown" and "why is the chat so slow" were searched for in the notes."""
    from tessellate.ai import intent

    for asked in ("how do i export everything to markdown", "why is the chat so slow", "how do i export my notes", "How do I back up my notes?"):
        assert intent.classify(asked) == intent.ABOUT_APP, asked
    for asked in ("how do i make sourdough", "why is the train so slow", "what did i write about the export deal"):
        assert intent.classify(asked) != intent.ABOUT_APP, asked


def test_why_is_the_chat_so_slow_in_chat_is_answered_by_the_guide(client):
    body = {"question": "why is the chat so slow", "use_tools": True, "history": []}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert "Performance mode" in text, text
