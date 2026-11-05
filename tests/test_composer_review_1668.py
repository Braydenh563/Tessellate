"""INBOX 1668 review: the class gaps an independent reviewer found in a, b and c
(INBOX 1357: fix the class). A refusal of an offer is its answer, not a repair;
a repair never calls a notes answer small talk; more ways to say a correction
and to ask for a reminder; the day rule on other seeds. Clock fixed at Wed 4 Nov
2026; model off and on alike (decision 75)."""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from tessellate.ai import reminder_parser, repair_turn
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 4, 10, 5)
OFFER = [{"question": "dentist", "answer": "Your check-up is on the 21st. Want me to add a reminder for the dentist?"}]
PLAIN = [{"question": "when is my dentist appointment", "answer": "Your check-up is on the 21st.[1]"}]
INTRO = ("Atlas's assistant", "I read your notes", "I answer from your notes", "What should the note say")


@pytest.fixture
def notebook(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.")
    session.commit()


REFUSALS = ["no I don't want that", "I don't need that", "no, I didn't ask for that", "i dont want it", "nope i dont need that"]


@pytest.mark.parametrize("said", REFUSALS)
def test_a_refusal_of_an_offer_is_its_answer_not_a_repair(client, notebook, said):
    text = _ask(client, said, history=OFFER)["text"]
    assert not text.startswith("Sorry") and "small talk" not in text and "Dentist" not in text and "21st" not in text, text


@pytest.mark.parametrize("said", REFUSALS)
def test_the_same_refusal_with_no_offer_before_it_is_a_repair(client, notebook, said):
    assert _ask(client, said, history=PLAIN)["text"].startswith("Sorry")


def test_a_notes_answer_is_never_called_small_talk(client, notebook):
    history = [{"question": "when is my dentist appointment", "answer": "Your check-up is on the 21st."}]
    text = _ask(client, "you've got that wrong", history=history)["text"]
    assert text.startswith("Sorry") and "small talk" not in text and "“when is my dentist appointment”" in text, text


def test_small_talk_before_a_correction_is_still_named_small_talk(client, notebook):
    history = [{"question": "test", "answer": "Loud and clear."}]
    assert "small talk" in _ask(client, "that's wrong", history=history)["text"]


MORE_REPAIRS = [
    "that isn't what i asked for", "not waht i asked", "i dont think thats right", "wrong. try again", "that was the wrong answer",
    "thats not what i asked for", "that wasnt what i asked", "taht is wrong", "not what i ask for", "i don't think that's correct",
    "that isnt right", "wrong, try again please",
]


@pytest.mark.parametrize("said", MORE_REPAIRS)
@pytest.mark.parametrize("kw", [{}, {"notes_only": True, "use_tools": False}])
def test_more_ways_to_say_a_correction_are_repair(client, notebook, said, kw):
    assert repair_turn.is_repair(said), said
    out = _ask(client, said, history=PLAIN, **kw)
    assert not out.get("grounding"), out
    if not kw:
        assert out["text"].startswith("Sorry") and "“when is my dentist appointment”" in out["text"], out["text"]


@pytest.mark.parametrize("said", ["that isn't what i asked for", "wrong. try again", "i dont think thats right"])
def test_a_model_running_makes_no_search_for_a_correction(ai_client, fake_ollama, notebook, said):
    out = _ask(ai_client, said, history=PLAIN, notes_only=True, use_tools=False)
    assert not out.get("grounding") and "Dentist" not in out["text"]


@pytest.mark.parametrize("said", ["what is wrong with the garden", "is that right for the dentist", "try the dentist note again", "think about the dentist"])
def test_a_question_or_a_request_is_not_a_correction(said):
    assert not repair_turn.is_repair(said)


ASKS = [
    "schedule a reminder", "setting a reminder, help", "I need to be reminded of something", "can you put a reminder in for me",
    "get me a reminder set up", "could you assist me in setting a reminder", "I want to be reminded", "scheduling a reminder please",
    "help me with setting up a reminder", "creating a reminder", "put a reminder in", "we need to be reminded of things",
]


@pytest.mark.parametrize("said", ASKS)
def test_more_asks_for_a_reminder_ask_what_and_when(client, notebook, said):
    assert reminder_parser.canonical_ask(said).lower().startswith("set a reminder"), said
    text = _ask(client, said)["text"]
    assert not any(w in text for w in INTRO) and "remind you about, and when" in text, text


@pytest.mark.parametrize("said", ASKS)
def test_the_same_asks_with_a_model_running(ai_client, fake_ollama, notebook, said):
    before = len(fake_ollama.chat_models)
    text = _ask(ai_client, said, notes_only=True, use_tools=False)["text"]
    assert "set a reminder" in text and not any(w in text for w in INTRO), text
    assert len(fake_ollama.chat_models) == before


@pytest.mark.parametrize(
    "said", ["put a reminder in for me tomorrow at 5pm to call mum", "schedule a reminder to pay rent on Friday at 9am"],
)
def test_an_ask_with_what_and_when_still_sets_it(client, notebook, said):
    assert _ask(client, said)["text"].startswith("Done. I will remind you"), said


@pytest.mark.parametrize("said", ["I need to be reminded of the dentist", "I set a reminder yesterday", "what reminders do I have", "I was reminded of Sam"])
def test_a_report_or_a_question_is_not_the_ask(said):
    assert reminder_parser.canonical_ask(said) == said


GYM = [
    ("Went to the gym for a quick cardio session", "2026-10-23T18:00:00"),
    ("Went to the gym on Monday and did deadlifts", "2026-11-02T18:00:00"),
    ("Back in September I went to the gym and did squats", "2026-09-10T18:00:00"),
]
_ABSOLUTE = re.compile(r"\b(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,? \d{1,2} \w+|\b\d{1,2} (?:Sep|Oct|Nov)\w*|\b(?:Sep|Oct|Nov)\w* \d{1,2}\b")


def _seed(session, monkeypatch, notes) -> None:
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for content, when in notes:
        entry = manager.create_entry(session, content, "Hobbies", [])
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
        manager.record_dates(session, entry, now=entry.created_at)
    session.commit()


def test_gym_events_say_a_relative_day_never_an_absolute_one(client, session, monkeypatch):
    _seed(session, monkeypatch, GYM)
    text = _ask(client, "gym notes", notes_only=True, use_tools=False)["text"]
    assert not _ABSOLUTE.search(text), text


def test_golf_two_days_ago_still_says_a_day(client, session, monkeypatch):
    _seed(session, monkeypatch, [("I had work and hit some golf balls as practice after haha", "2026-10-04T20:00:00"),
                                 ("Played a game of golf for 18 holes at Windaroo which was fun, I shot like 130", "2026-11-02T18:00:00")])
    told = [p for p in _ask(client, "golf notes", notes_only=True, use_tools=False)["text"].split("\n\n") if not p.startswith("You have")]
    assert len(told) == 2 and re.search(r"ago|last|Monday|Sunday|days", told[0]) and re.search(r"ago|last|Monday|Sunday|days|yesterday", told[1], re.I), told
