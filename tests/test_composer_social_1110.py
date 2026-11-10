"""F4 of the 1110 audit, no model, clock fixed at Tuesday 10 November 2026, 09:00.

Social turns (greetings, how are you, feelings) get a short warm line that
varies by turn and never quotes a note; meta turns ("shorter", "say that
again", "simpler") act on the previous answer; a comparison follow-on
("which is higher") binds to the previous answer's numbers."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


HELLO = [{"question": "hi", "answer": "Hello. What would you like to look up?"}]
TIRED = "feeling pretty tired"
LONG = (
    "The dentist moved your appointment to Thursday 12 November at 3pm. You also wrote that the night guard "
    "is ready to collect. The cleaning costs 80 pounds."
)
LAST = [{"question": "what did the dentist say", "answer": LONG}]
NUMBERS = [{"question": "what did I spend", "answer": "You spent 40 pounds on food and 85 pounds on the train this week."}]


def _bad(text):
    low = text.lower()
    return (
        not text.strip()
        or TIRED in low
        or "your own words" in low
        or "no note" in low
        or "don't mention" in low
        or "appreciated" in low
        or "](#/notes/" in text
        or "**" in text
    )


@pytest.mark.parametrize(
    "ask",
    ["how are you", "how are you doing", "how's it going", "thanks for listening", "you're not very helpful", "i love you", "i miss anna"],
)
def test_a_social_turn_after_hi_is_never_a_note_quote(go, ask):
    text, _ = go(ask, history=HELLO)
    assert not _bad(text), text


@pytest.mark.parametrize("ask", ["i feel sick", "i can't focus", "i'm stressed about the exam", "i feel awful"])
def test_a_feeling_gets_a_warm_line_not_a_thank_you_or_a_search(go, ask):
    text, _ = go(ask)
    assert not _bad(text), text


def test_a_feeling_is_answered_differently_on_a_later_turn(go):
    first, _ = go("i feel sick")
    second, _ = go("i feel sick", history=[{"question": "i feel sick", "answer": first}])
    third, _ = go("i feel sick", history=[{"question": "i feel sick", "answer": first}, {"question": "i feel sick", "answer": second}])
    assert len({first, second, third}) == 3, (first, second, third)


def test_shorter_acts_on_the_previous_answer(go):
    text, _ = go("shorter", history=LAST)
    assert text.strip() and len(text) < len(LONG) and text.split(".")[0] in LONG, text


@pytest.mark.parametrize("ask", ["say that again", "can you repeat that", "what did you just say"])
def test_again_repeats_the_previous_answer(go, ask):
    text, _ = go(ask, history=LAST)
    assert LONG in text, text


def test_simpler_reads_the_previous_answer_in_plainer_words(go):
    text, _ = go("simpler", history=LAST)
    assert text.strip() and len(text) <= len(LONG) and "](#/notes/" not in text, text


def test_a_comparison_binds_to_the_previous_answers_numbers(go):
    text, _ = go("which is higher", history=NUMBERS)
    assert "85" in text and "train" in text.lower() and "general knowledge" not in text.lower(), text
    text, _ = go("which is lower", history=NUMBERS)
    assert "40" in text and "food" in text.lower(), text
