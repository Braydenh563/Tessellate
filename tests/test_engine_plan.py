"""The query plan, the routing and the utilities (CHAT_PLAN Phase 6 step 2,
decisions 31 and 41; the engine probe's intent table, 2026-10-10)."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from tessellate.ai import composer, intent, utilities
from tessellate.core import deps
from tessellate.core.config import user_now
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

SEED = json.loads((Path(__file__).parent / "fixtures" / "composer" / "phase6_seed.json").read_text(encoding="utf-8"))
TODAY = date.fromisoformat(SEED["today"])
NOW = datetime(2026, 10, 6, 14, 30)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("how do I change the theme", intent.ABOUT_APP),
        ("where is the export button", intent.ABOUT_APP),
        ("what is memorymap", intent.ABOUT_APP),
        ("can you help me", intent.ABOUT_APP),
        ("help", intent.ABOUT_APP),
        ("what's new", intent.ABOUT_APP),
        ("what is 12*7", intent.UTILITY),
        ("what time is it", intent.UTILITY),
        ("translate hello to french", intent.UTILITY),
        ("what's the weather", intent.UTILITY),
        ("tell me a joke", intent.SMALLTALK),
        #: Identity, answered as the assistant (decision 36) rather than the Guide.
        ("are you an ai", intent.SMALLTALK),
        ("asdfgh", intent.SMALLTALK),
        # Held: a how-to about the person's own subject is a notes question.
        ("how do I cook rice", intent.NOTES),
        ("where is the spare key", intent.NOTES),
        ("how many days until the dentist", intent.NOTES),
        ("tower", intent.NOTES),
    ],
)
def test_the_router(message, expected):
    assert intent.classify(message) == expected


@pytest.mark.parametrize(
    ("message", "kind"),
    [("tell me a joke", "joke"), ("asdfgh", "unclear"), ("are you an ai", "who")],
)
def test_the_reply_kind(message, kind):
    assert composer.social_kind(message, intent.classify(message)) == kind
    assert composer.social(message, intent.classify(message)) in composer.social_surfaces(kind)


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        ("what did I do last week", "recall"),
        ("what did I write yesterday", "recall"),
        ("why does the sync rule drop edits", "why"),
        ("how do I cook rice", "how"),
        ("compare the gym plan and the gym log", "comparison"),
        ("how many sets did I do", "count"),
        ("is the dentist booked", "yesno"),
        ("what is the latest on harbor", "status"),
        ("what should I do about the shed roof", "recommendation"),
        ("any patterns in my golf notes", "insight"),
        ("list my reading list", "list"),
        ("when is the dentist", "when"),
        ("who did I meet on Friday", "fact"),
        ("what is 12 * 7", "utility"),
    ],
)
def test_the_plan_kind(question, kind):
    assert composer.plan(question, TODAY).kind == kind


def test_a_subject_with_a_window_is_answered_from_the_window_not_listed():
    p = composer.plan("what did I do at the gym last week", TODAY)
    assert p.kind != "recall" and p.window == (date(2026, 9, 28), date(2026, 10, 4)) and p.terms == ["gym"]


def test_the_plan_carries_the_length_wish():
    assert composer.plan("briefly, when is the dentist", TODAY).length == "brief"


def _compose(question, notes=None, **kw):
    return composer.compose(question, SEED["notes"] if notes is None else notes, today=TODAY, **kw)


def test_recall_lists_the_window_newest_first_under_its_count():
    result = _compose("what did I do the week before last")
    assert result["shape"] == "recall"
    assert result["text"].startswith("You wrote five notes the week before last, newest first:")
    days = [line.split("(")[1].split(")")[0] for line in result["text"].splitlines()[1:]]
    assert days == ["27 September", "27 September", "26 September", "25 September", "24 September"]
    assert all(row["sentence"] in result["text"] for row in result["grounding"])


def test_recall_says_when_the_window_is_empty():
    result = _compose("what did I write in March")
    assert result["text"] == "Nothing I found was written in March."
    assert not result["grounding"]


def test_a_window_keeps_the_answer_to_its_notes():
    result = _compose("what did I do at the gym last week")
    assert {row["note_id"] for row in result["grounding"]} == {1}


def test_a_tag_no_note_carries_is_said():
    assert _compose("notes tagged chess")["text"] == "No note found is tagged “chess”."


def test_a_tag_keeps_the_answer_to_its_notes():
    result = _compose("what do my notes tagged golf say")
    assert {row["note_id"] for row in result["grounding"]} <= {3, 4, 5, 6}


# --- utilities (decision 41) --------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "first"),
    [
        ("what is 12 * 7", "12 * 7 is 84."),
        ("what time is it", "It is 14:30 on Tuesday 6 October 2026."),
        ("what day is it today", "Today is Tuesday 6 October 2026."),
        ("convert 5 miles to km", "5 miles is 8.05 kilometres."),
        ("how many km is 5 miles", "5 miles is 8.05 kilometres."),
        ("5 km in miles", "5 kilometres is 3.11 miles."),
        ("100 f to c", "100 °F is 37.78 °C."),
        ("how many cups in a litre", "1 litre is 4.23 cups."),
        ("2 feet to inches", "2 feet is 24 inches."),
        ("80 kg in pounds", "80 kilograms is 176.37 pounds."),
        ("how much is 100 dollars in euros", "100 USD is about 88 EUR at the rates from 1 June 2025."),
        ("how many days until christmas", "Friday 25 December 2026 is 80 days away."),
        ("how many days since 1 March", "Sunday 1 March 2026 was 219 days ago."),
        ("what day is 25 December", "25 December 2026 is a Friday."),
        ("what date is it in 3 weeks", "3 weeks from today is Tuesday 27 October 2026."),
        ("5 kg to miles", "Kilograms and miles measure different things (mass and length), so one does not convert to the other."),
    ],
)
def test_a_utility_answers_one_computed_sentence(question, first):
    parts = utilities.answer(question, NOW)
    assert parts and parts[0] == ("computed", first)


def test_a_conversion_says_how_it_read_the_question():
    parts = utilities.answer("how many km is 5 miles", NOW)
    assert parts[1] == ("computed", "\nRead as 5 miles in kilometres.")


def test_chance_is_in_range_and_the_same_for_a_salt():
    for salt in ("a", "b", "c", "d"):
        roll = utilities.answer("roll a die", NOW, salt)[0][1]
        assert roll == utilities.answer("roll a die", NOW, salt)[0][1]
        assert 1 <= int(roll.split()[-1].rstrip(".")) <= 6
        pick = int(utilities.answer("pick a number between 3 and 5", NOW, salt)[0][1].rstrip("."))
        assert 3 <= pick <= 5


@pytest.mark.parametrize(
    "hostile",
    ["what is __import__('os').system('ls')", "what is 9**9**9", "what is 10 ** 1000", "what is (1).__class__", "calculate 2 ** 99999999"],
)
def test_hostile_sums_are_refused_quickly(hostile):
    started = time.perf_counter()
    assert utilities.answer(hostile, NOW) is None
    assert time.perf_counter() - started < 0.05


@pytest.mark.parametrize("question", ["what is the capital of Peru", "how many days until the dentist", "what time is the dentist"])
def test_not_a_utility(question):
    assert utilities.answer(question, NOW) is None


def test_the_weather_is_said_not_known_never_guessed():
    result = composer.compose("what's the weather like", [], today=TODAY)
    assert result["text"] == composer.PHRASES["utility_weather"] and result["shape"] == "utility"


# --- the route ------------------------------------------------------------------------


def test_a_utility_is_worked_out_even_with_a_model_running(ai_client, fake_ollama, session):
    """Worked out by the engine, model or not. Changed 2026-10-27 (decision 75,
    the owner: the model writes every answer when it runs): the result now
    goes to the model as a fact (`_fact_events`), and a reply without the
    figure, as the fake's is, leaves the engine's sentence with no model named
    under it (the latest `meta`). The model-written case is
    `tests/test_model_writes_facts_1027.py`."""
    out = _ask(ai_client, "what is 12 * 7", use_tools=False)
    assert "84" in json.dumps(fake_ollama.chat_calls[-1])
    assert out["text"] == "12 * 7 is 84."
    assert out["meta"][-1]["answered_by"] is None
    assert fake_ollama.librarian_reply not in out["text"]


def test_the_time_is_the_persons_clock(client, session):
    out = _ask(client, "what time is it", use_tools=False)
    now = user_now(deps.get_config())
    assert out["text"].startswith("It is ") and str(now.year) in out["text"]


def test_recall_by_time_reads_every_note_of_the_window(client, session):
    now = user_now(deps.get_config()).replace(tzinfo=None)
    last_monday = (now - timedelta(days=now.weekday() + 7)).replace(hour=10)
    for i in range(7):
        entry = manager.create_entry(session, f"# Day {i}\n\nWorked on item number {i} of the list.")
        entry.created_at = last_monday + timedelta(days=i)
    old = manager.create_entry(session, "# Old\n\nSomething from long ago.")
    old.created_at = now - timedelta(days=60)
    session.commit()
    out = _ask(client, "what did I do last week", notes_only=True, use_tools=False, answer_from="notes")
    #: Since owner-1026b K20 the answer is the activity recap (every kind,
    #: grouped by day); the window still holds every note of it and no other.
    assert out["text"].startswith("Last week (") and "you made seven notes:" in out["text"], out["text"]
    assert all(f"**Day {i}**" in out["text"] for i in range(7)) and "**Old**" not in out["text"]


# Utilities worked out with no model and no search (CHAT_PLAN A1). The eval
# set (fixtures/composer/utilities_1011.json) is 60 ways of asking a sum, a
# list's average, a root, a time in another city, a countdown, a month's days
# or an age. Each is answered with a "Read as" line that says how the question
# was read; the not_utilities stay questions for the notes.

UTILITIES_EVAL = json.loads((Path(__file__).parent / "fixtures/composer/utilities_1011.json").read_text(encoding="utf-8"))
UTIL_NOW = datetime(2026, 10, 11, 10, 0)


def test_the_eval_set_is_sixty_phrasings():
    assert len(UTILITIES_EVAL["utilities"]) >= 60 and len(UTILITIES_EVAL["not_utilities"]) >= 10


def test_at_least_ninety_five_percent_are_worked_out_and_say_how_they_were_read():
    answered = [q for q in UTILITIES_EVAL["utilities"] if (utilities.answer(q, now=UTIL_NOW) or [])]
    assert len(answered) / len(UTILITIES_EVAL["utilities"]) >= 0.95
    #: A sum typed in symbols ("12 * 7") is its own reading; everything else says how it was read.
    unread = [q for q in answered if "\nRead as " not in "".join(t for _, t in utilities.answer(q, now=UTIL_NOW))]
    assert all(utilities.kind_of(q) == "sum" and any(c in q for c in "+*/^%x") for q in unread), unread


@pytest.mark.parametrize("question", UTILITIES_EVAL["not_utilities"])
def test_a_notes_question_is_not_a_utility(question):
    assert utilities.kind_of(question) is None


@pytest.mark.parametrize(("question", "said"), [
    ("whats 5 plus 5", "5 + 5 is 10."),
    ("2 to the power of 8", "is 256."),
    ("square root of 81", "The square root of 81 is 9."),
    ("average of 3, 8, 10", "The average of 3, 8, 10 is 7."),
    ("median of 1, 5, 9 and 12", "is 7."),
    ("9am London in Tokyo", "09:00 in London is 17:00 in Tokyo."),
    ("how many days in February 2028", "February 2028 has 29 days."),
    ("how old is someone born in 1990", "36 this year"),
    ("days until christmas", "75 days away."),
])
def test_the_worked_answer(question, said):
    assert said in "".join(t for _, t in utilities.answer(question, now=UTIL_NOW))


def test_every_utility_routes_as_one():
    assert [q for q in UTILITIES_EVAL["utilities"] if intent.classify(q) != intent.UTILITY] == []
