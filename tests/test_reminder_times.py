"""Magic Add and the clock (reported bug).

Reported directly: *"I just put a sentence in the magic add text box in
reminders saying 'play league of legends in half an hour' and it scheduled it
for 10am tomorrow??"*

Two separate faults, and the phrase was the smaller one.

**The timezone frame.** The route built the user's clock as `utcnow() + offset`,
which is an aware datetime TAGGED UTC that actually holds local wall-clock. The
model was therefore told "now is 2026-08-01T23:30:00+00:00" when that +00:00 was
a fiction. A model that answered with an offset of its own, the natural thing
to do, having been handed one, was then trusted and skipped the correction, so
the reminder landed out by exactly the user's UTC offset. At UTC+10 that turns
"half an hour" into ten and a half hours: 10am the next day, exactly as
reported.

**The delegation.** "in half an hour" is arithmetic, and it was being handed to
a 3B model, so the answer varied with whichever model happened to be installed.
It is resolved by rule now, before the model is consulted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tessellate.ai import reminder_parser
from tests._frozen_clock import FIXED_NOW, freeze_reminder_clock


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    freeze_reminder_clock(monkeypatch)


# --- the reported sentence --------------------------------------------------

BRISBANE = 600  # UTC+10, minutes east, the sign the frontend sends


def _due(client, text: str, offset: int = BRISBANE) -> datetime:
    response = client.post(
        "/reminders/parse", json={"text": text, "tz_offset_minutes": offset}
    )
    assert response.status_code == 201, response.text
    return datetime.fromisoformat(response.json()["due_at"])


def _minutes_away(due: datetime) -> float:
    return (due - FIXED_NOW).total_seconds() / 60


def test_the_reported_sentence_lands_half_an_hour_away(client):
    """The whole bug, in one assertion."""
    due = _due(client, "play league of legends in half an hour")
    assert 28 <= _minutes_away(due) <= 32


def test_the_reported_sentence_does_not_land_tomorrow_morning(client):
    """Stated separately because "roughly right" and "not 10am tomorrow" are
    different claims, and it was the second one that was wrong."""
    due = _due(client, "play league of legends in half an hour")
    local = due + timedelta(minutes=BRISBANE)
    assert local.date() == (FIXED_NOW + timedelta(minutes=BRISBANE)).date() or (
        _minutes_away(due) < 60
    ), "the reminder rolled over to another day"


def test_the_time_phrase_is_taken_out_of_the_reminder_text(client):
    """It is a reminder to play league of legends. Leaving "in half an hour" in
    the text would have it still saying so when it fires."""
    response = client.post(
        "/reminders/parse",
        json={"text": "play league of legends in half an hour", "tz_offset_minutes": BRISBANE},
    )
    text = response.json()["text"].lower()
    assert "league of legends" in text
    assert "half an hour" not in text


# --- the timezone frame -----------------------------------------------------


@pytest.mark.parametrize("offset", [0, 600, -480, 330, -210])
def test_the_offset_does_not_move_a_relative_reminder(client, offset):
    """"In 30 minutes" is 30 minutes away from whichever chair you are sitting
    in. Before the fix the error was exactly the offset, so a user in UTC+10
    saw ten hours of it and a user in UTC saw none, which is why this went
    unnoticed for so long."""
    due = _due(client, "do the thing in 30 minutes", offset=offset)
    assert 28 <= _minutes_away(due) <= 32


def test_the_model_is_told_a_clock_that_is_actually_true(ai_client, monkeypatch):
    """The root cause: `utcnow() + offset` is tagged UTC but holds local
    wall-clock, so the offset it advertises is a fiction."""
    seen = {}

    def _capture(text, ollama, model_manager, now):
        seen["now"] = now
        return {"text": text, "due_at": now + timedelta(hours=1), "priority": "normal"}

    monkeypatch.setattr(reminder_parser, "parse_reminder", _capture)
    ai_client.post(
        "/reminders/parse",
        json={"text": "something at some point", "tz_offset_minutes": BRISBANE},
    )
    now = seen["now"]
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(minutes=BRISBANE), (
        "the clock handed to the parser still advertises the wrong offset"
    )


def test_an_answer_that_carries_its_own_offset_is_not_double_counted(ai_client, monkeypatch):
    """The branch that actually caused the report. A model given a timezone
    naturally answers with one; that reply used to be trusted as-is, skipping
    the correction the naive branch applied."""

    def _aware(text, ollama, model_manager, now):
        return {"text": text, "due_at": now + timedelta(minutes=30), "priority": "normal"}

    monkeypatch.setattr(reminder_parser, "parse_reminder", _aware)
    due = _due(ai_client, "something at some point")
    assert 28 <= _minutes_away(due) <= 32


def test_a_naive_answer_is_read_in_the_users_zone(ai_client, monkeypatch):
    def _naive(text, ollama, model_manager, now):
        return {
            "text": text,
            "due_at": (now + timedelta(minutes=30)).replace(tzinfo=None),
            "priority": "normal",
        }

    monkeypatch.setattr(reminder_parser, "parse_reminder", _naive)
    due = _due(ai_client, "something at some point")
    assert 28 <= _minutes_away(due) <= 32


# --- the rules themselves ---------------------------------------------------


@pytest.mark.parametrize(
    ("phrase", "minutes"),
    [
        ("in half an hour", 30),
        ("in a half hour", 30),
        ("in 30 mins", 30),
        ("in 20 minutes", 20),
        ("in 45 min", 45),
        ("in an hour", 60),
        ("in 1 hour", 60),
        ("in 2 hours", 120),
        ("in a couple of hours", 120),
        ("in a couple hours", 120),
        ("in a few minutes", 3),
        ("in an hour and a half", 90),
        ("in a quarter of an hour", 15),
        ("in 3 days", 3 * 24 * 60),
        ("in 1 week", 7 * 24 * 60),
    ],
)
def test_the_shapes_people_actually_type(phrase, minutes):
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    parsed = reminder_parser.parse_relative(f"do the thing {phrase}", now)
    assert parsed is not None, f"{phrase!r} was not understood"
    assert parsed["due_at"] - now == timedelta(minutes=minutes)


@pytest.mark.parametrize(
    ("text", "due", "kept"),
    [
        ("call bob in 2 days at 3pm", (2026, 8, 3, 15, 0), "call bob"),
        ("in 3 days at 9:30 water the plants", (2026, 8, 4, 9, 30), "water the plants"),
        ("check the post in a week at noon", (2026, 8, 8, 12, 0), "check the post"),
    ],
)
def test_a_day_offset_keeps_the_clock_that_was_said(text, due, kept):
    """"In 2 days at 3pm" was 12:00 in two days: the offset was taken and the
    time said beside it was dropped, so the reminder fired at the wrong hour
    with no word of it."""
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    parsed = reminder_parser.parse_relative(text, now)
    assert parsed is not None
    assert parsed["due_at"] == datetime(*due, tzinfo=timezone.utc)
    assert parsed["text"].lower() == kept


@pytest.mark.parametrize(
    "phrase",
    ["at 8pm", "tomorrow morning", "next tuesday", "on the 5th", "sometime soon"],
)
def test_wall_clock_phrases_are_left_to_the_model(phrase):
    """These name a target rather than an offset, so they need the user's date
    as well as their clock. Half-implementing them here is how the original
    bug happened; the model handles them, now inside a frame that is true."""
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    assert reminder_parser.parse_relative(f"do the thing {phrase}", now) is None


def test_a_nonsense_duration_is_declined_rather_than_scheduled():
    """A year out is not a reminder, it is a typo with consequences."""
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    assert reminder_parser.parse_relative("do it in 9999 days", now) is None
    assert reminder_parser.parse_relative("do it in 0 minutes", now) is None


def test_the_rule_beats_the_model_rather_than_the_other_way_round(app_state):
    """Arithmetic should not vary with which model happens to be installed."""

    class Exploding:
        def chat(self, *a, **k):
            raise AssertionError("the model was asked to do arithmetic")

    parsed = reminder_parser.parse_reminder(
        "do the thing in 30 minutes",
        Exploding(),
        None,
        datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
    )
    assert parsed["due_at"] == datetime(2026, 8, 1, 12, 30, tzinfo=timezone.utc)


# --- and it works with the AI switched off ----------------------------------


def test_a_relative_reminder_works_with_ollama_off(client):
    """Design principle 2: the app works when the AI doesn't. Refusing
    "remind me in 20 minutes" because Ollama is off asks a model for
    arithmetic. (`client` is the fixture with all AI unavailable.)"""
    due = _due(client, "take the bins out in 20 minutes")
    assert 18 <= _minutes_away(due) <= 22


def test_a_phrase_needing_the_model_still_says_so_when_it_is_off(client):
    """Degrading gracefully is not the same as pretending: a phrase neither
    reader understands, with no model behind it, has to be refused, and
    usefully."""
    response = client.post(
        "/reminders/parse",
        json={"text": "call the dentist when the kettle boils", "tz_offset_minutes": BRISBANE},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "in 20 minutes" in detail, "the error should show a form that works"
    assert "tomorrow at 5pm" in detail, "and a wall-clock form that works too"


# --- wall-clock phrases with no model (audit 2026-10-05, UX-01) -------------
#
# `ai/when.resolve` reads these with no model, but Magic Add only tried the
# "in N units" rule before demanding one, so the dashboard's "Remind me: say
# when, in plain words" was a dead end on the default install.

UTC = 0


@pytest.mark.parametrize(
    ("text", "kept", "gone", "day_offset", "hour"),
    [
        ("call mum tomorrow at 5pm", "call mum", "tomorrow", 1, 17),
        ("dentist next Friday at 3pm", "dentist", "friday", None, 15),
        ("pay rent on 1 November", "pay rent", "november", None, 9),
        ("water plants tonight", "water plants", "tonight", None, 20),
        ("call the dentist at 3pm on thursday", "call the dentist", "thursday", None, 15),
        ("Remind me to stretch this evening", "stretch", "evening", None, 18),
    ],
)
def test_wall_clock_phrases_work_with_the_ai_off(client, text, kept, gone, day_offset, hour):
    response = client.post("/reminders/parse", json={"text": text, "tz_offset_minutes": UTC})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["text"].lower() == kept, body["text"]
    assert gone not in body["text"].lower()
    due = datetime.fromisoformat(body["due_at"]).astimezone(timezone.utc)
    now = FIXED_NOW
    if gone in ("tonight", "evening") and now.hour >= hour:
        #: Said after the hour, "tonight" is the next whole hour, not a time gone by.
        hour = (now.hour + 1) % 24
    assert due.hour == hour and due.minute == 0
    if day_offset is not None:
        assert due.date() == (FIXED_NOW + timedelta(days=day_offset)).date()


def test_a_wall_clock_phrase_is_read_on_the_users_clock(client):
    """5pm in Brisbane is 07:00 UTC, not 17:00 UTC."""
    due = _due(client, "call mum tomorrow at 5pm", offset=BRISBANE)
    assert due.astimezone(timezone.utc).hour == 7


def test_the_rules_are_tried_before_the_model(ai_client, monkeypatch):
    """Arithmetic should not vary with the installed model, wall-clock or not."""

    def _never(*a, **k):
        raise AssertionError("the model was asked for a time the rules read")

    monkeypatch.setattr(reminder_parser, "parse_reminder", _never)
    response = ai_client.post(
        "/reminders/parse", json={"text": "call mum tomorrow at 5pm", "tz_offset_minutes": UTC}
    )
    assert response.status_code == 201


def test_a_reminder_that_is_only_a_time_keeps_a_name():
    from tessellate.ai import when

    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    parsed = when.parse_reminder_text("tomorrow at 5pm", now)
    assert parsed is not None and parsed["text"]


def test_the_placeholder_example_reads_its_priority_too():
    from tessellate.ai import when

    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    parsed = when.parse_reminder_text("Call mum tomorrow evening, high priority", now)
    assert parsed["text"] == "Call mum"
    assert parsed["priority"] == "high"
    assert parsed["due_at"] == datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "text, kept, recurring",
    [
        ("water the plants every tuesday", "water the plants", "weekly"),
        ("every morning at 7 stretch", "stretch", "daily"),
        ("remind me in 20 minutes to check the oven", "check the oven", "none"),
    ],
)
def test_magic_add_keeps_the_words_and_the_repeat(client, text, kept, recurring):
    """The engine probe's reminder rows (CHAT_PLAN F1): "every tuesday" was
    saved once as "Water the plants every"; "every morning at 7" at 19:00."""
    response = client.post("/reminders/parse", json={"text": text, "tz_offset_minutes": UTC})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["text"].lower() == kept
    assert body["recurring"] == recurring
    if "morning at 7" in text:
        assert datetime.fromisoformat(body["due_at"]).astimezone(timezone.utc).hour == 7
