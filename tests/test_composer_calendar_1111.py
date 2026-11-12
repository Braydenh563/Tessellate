"""A calendar or a to-do list said in other words is the reminder act, or a plain how-to when it would empty the lot."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import act_registry, commands, composer_calendar

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.mark.parametrize(
    ("said", "intent", "text"),
    [
        ("add farm trip to my calendar for friday", "reminder", "Farm trip"),
        ("i must add farm trip to my calendar for friday", "reminder", "Farm trip"),
        ("i need to put my appointment for tomorrow on my calendar", "reminder", "my appointment"),
        ("add my dentist appointment to the calendar", "reminder", "dentist appointment"),
        ("put clean stovetop on my list of reminders", "reminder", "Clean stovetop"),
        ("please also list wash laundry on my to do list", "reminder", "Wash laundry"),
        ("put clean refrigerator on my spring cleaning to do list", "reminder", "Clean refrigerator"),
        ("i'd like to have a reminder made", "reminder", ""),
        ("remove celebrate anniversary from my calendar", "cancel", None),
        ("take my dinner plans off my calendar for tomorrow", "cancel", None),
        ("can you check washing the dishes off on my to do list", "complete", None),
    ],
)
def test_said_in_other_words_is_the_act(said, intent, text):
    found = commands.read(said, NOW)
    assert found and found["intent"] == intent, found
    if text is not None:
        assert text.lower() in found["text"].lower() or not text


@pytest.mark.parametrize(
    "said",
    ["clear my calendar for this friday", "clear out my entire todo list", "hey just take off everything from my todo list", "empty my calendar"],
)
def test_emptying_a_whole_list_is_a_how_to_and_never_done(said):
    assert composer_calendar.bulk(said)
    assert act_registry.app_verb(said) == "clear"
    assert commands.read(said, NOW) is None
    assert "cancel the reminder about" in act_registry.app_verb_line("clear")


@pytest.mark.parametrize("said", ["add milk to the shopping list", "what is on my calendar", "clear the cache", "delete the lentil soup note"])
def test_other_sentences_are_left_alone(said):
    assert not composer_calendar.bulk(said)
    assert composer_calendar.restate(said) == said


@pytest.mark.parametrize(
    "said", ["I need to set an alarm.", "Please can I add a new alarm.", "I would like to put in another alarm.", "Can you add an alarm for four in the evening?"]
)
def test_setting_an_alarm_is_the_reminder_act(said):
    found = commands.read(said, NOW)
    assert found and found["intent"] == "reminder", found


def test_a_question_about_the_alarm_code_is_left_alone():
    assert composer_calendar.restate("what is the alarm code at the office") == "what is the alarm code at the office"
