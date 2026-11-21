"""2026-10-30 composer sweep, each a class of question answered wrong:

- a when-question matched its timing verb, not its subject ("when are the
  designs coming" answered with the plumber who is coming Thursday);
- "how many notes mention X" gave a dated line, not the count;
- "how hot do I bake" said no note mentions "hot";
- "what am I doing on the 17th" read the 17th as the day gone.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from tessellate.ai import composer_plan
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)
NOTES = [
    "# Lisbon trip\n\nFlying out on 14 November, back on the 21st. Staying in Alfama. Day trip to Sintra on the 17th.",
    "# Lisbon packing list\n\n- [x] passport\n- [ ] adapter",
    "# Sourdough\n\nFeed the starter at 9pm. Bake at 230C for 40 minutes with the lid on, then 15 without.",
    "# Meeting with Sara\n\nSara wants the beta by 15 November. She will send the designs on Monday.",
    "# Car\n\nService due in January. The tyres were replaced on 2 September for $480.",
    "Called the plumber, he is coming Thursday at 10 to fix the leak under the sink.",
    "# Ideas\n\nLearn Portuguese before Lisbon. Start a herb garden.",
    "# Book club\n\nNext book is Piranesi. Meeting at Ana's on the first Sunday of the month.",
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for content in NOTES:
        manager.create_entry(session, content)
    session.commit()

    def go(question: str) -> str:
        body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
        text = ""
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if line.strip():
                    event = json.loads(line)
                    if event["type"] == "answer":
                        text += event["delta"]
        return text

    return go


@pytest.mark.parametrize(("question", "said", "never"), [
    ("when are the designs coming", "Monday", "plumber"),
    ("when is the beta due", "15 November", "Service"),
])
def test_a_when_question_is_answered_by_its_subject_not_its_timing_word(ask, question, said, never):
    answer = ask(question)
    first = answer.split("\n")[0]
    assert said in first and never not in first, answer


@pytest.mark.parametrize("question", ["how many notes do I have about lisbon", "how many notes mention lisbon"])
def test_how_many_notes_leads_with_the_count_and_the_name_as_written(ask, question):
    first = ask(question).split("\n")[0]
    assert first.startswith("You have three notes about Lisbon"), first


def test_how_hot_says_the_temperature(ask):
    first = ask("how hot do I bake the sourdough").split("\n")[0]
    assert "230C" in first and "hot" not in first, first


@pytest.mark.parametrize("question", ["what am I doing on the 17th", "what do I have on the 17th"])
def test_a_day_asked_in_the_present_is_the_one_to_come(ask, question):
    said = ask(question)
    assert "17 November" in said and "Sintra" in said, said


@pytest.mark.parametrize(("question", "day"), [
    ("what am I doing on the 17th", date(2026, 11, 17)),
    ("what do I have on the 17th", date(2026, 11, 17)),
    ("what was I doing on the 17th", date(2026, 10, 17)),
    ("what did I have on the 17th", date(2026, 10, 17)),
])
def test_the_tense_picks_which_17th(question, day):
    assert composer_plan.window(question, date(2026, 10, 30))[0] == day


@pytest.mark.parametrize(("message", "route"), [
    ("what should I ask the dentist", "notes"), ("how can I help Jake move house", "notes"),
    ("did Sam help with the garden", "notes"), ("what are you doing on friday sara said", "notes"),
    ("what should i ask", "about_app"), ("hey what can you do", "about_app"), ("help", "about_app"),
    ("so what can you do exactly", "about_app"), ("what kind of stuff can you help with", "about_app"),
    ("what kind of stuff did Sam help with", "notes"), ("can you help me with my essay", "notes"),
])
def test_an_app_phrase_inside_a_notes_question_is_not_about_the_app(message, route):
    """2026-10-30 sweep: "what should I ask the dentist" got the app's own
    blurb; a phrase about the app counts only when it ends the message."""
    from tessellate.ai import intent

    assert intent.classify(message) == route


def test_a_thing_done_on_a_day_is_this_years_day(client, session, monkeypatch):
    """"Planted tomatoes on 5 October" in a note of 30 October 2026 was said
    back as 5 October 2027."""
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    manager.create_entry(session, "# Garden\n\nPlanted tomatoes and basil on 5 October. Water every second day.")
    session.commit()
    body = {"question": "when did I plant the tomatoes", "answer_from": "notes", "notes_only": True, "use_tools": False}
    said = ""
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip() and (event := json.loads(line))["type"] == "answer":
                said += event["delta"]
    assert "5 October" in said and "2027" not in said, said


@pytest.mark.parametrize("question", ["where is book club", "where's the book club?", "where do we meet for book club"])
def test_a_where_question_leads_with_the_place(ask, question):
    """The sentence that names a place leads, not the first one about the
    subject (2026-10-30 sweep)."""
    assert ask(question).startswith("Meeting at Ana's"), question
