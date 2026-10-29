"""Composer grading round (INBOX 1324 and 1315): classes the 40-question
catalogue (`scratchpad/composer1324-grades.md`) found wrong with no model."""

from __future__ import annotations

import pytest

from tessellate.ai import composer
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


@pytest.mark.parametrize(("plural", "single"), [("knives", "knife"), ("shelves", "shelf"), ("loaves", "loaf"), ("wives", "wife")])
def test_an_irregular_plural_meets_its_singular(plural, single):
    assert composer._stem(plural) == composer._stem(single)


@pytest.mark.parametrize("ask", ["which notes mention the boiler", "find notes about the boiler", "show me notes on the boiler"])
def test_ask_answers_a_find_from_the_notes_and_does_not_send_it_to_chat(client, session, ask):
    manager.create_entry(session, "# Boiler service\n\nDue in November; mention the pressure.")
    session.commit()
    text = _ask(client, ask, notes_only=True, use_tools=False)["text"]
    assert "Boiler service" in text
    assert "say it in Chat" not in text


@pytest.mark.parametrize(
    ("ask", "name"),
    [
        ("how many notes do I have", ""),
        ("how many notes do I have about work?", "work"),
        ("how many work notes do I have", "work"),
        ("how many notes are in Cooking", "Cooking"),
        ("how many notes tagged harbor", "harbor"),
    ],
)
def test_a_count_of_notes_is_read_as_a_count(ask, name):
    from tessellate.ai import composer_lists

    assert composer_lists.counted_filing(ask) == name


def test_how_many_asked_for_something_else_is_not_a_note_count():
    from tessellate.ai import composer_lists

    assert composer_lists.counted_filing("how many beta testers are active") is None


@pytest.mark.parametrize("surface", [{"notes_only": True}, {"use_tools": False}])
def test_how_many_notes_is_answered_with_the_figure(client, session, surface):
    from tessellate.entry import manager as m

    for i in range(3):
        m.create_entry(session, f"# Task {i}\n\nA work note {i}.", category_name="Work")
    m.create_entry(session, "# Soup\n\nStock and onions.", category_name="Cooking")
    session.commit()
    text = _ask(client, "how many notes do I have about work", **surface)["text"]
    assert "You have 3 notes in Work" in text and "Heads up" not in text
    assert "You have 4 notes" in _ask(client, "how many notes do I have", **surface)["text"]


def test_a_subject_inside_a_window_keeps_the_window(client, session):
    from datetime import datetime, timedelta

    from tessellate.entry import manager as m

    old = m.create_entry(session, "# Sourdough old\n\nStarter fed at night, ready by morning.")
    new = m.create_entry(session, "# Sourdough new\n\nSixth loaf, 78% hydration and a 20 hour cold proof.")
    today = datetime.now()
    old.created_at = today - timedelta(days=40)
    new.created_at = (today - timedelta(days=today.weekday() + 5)).replace(hour=12)  # last week's Wednesday
    session.commit()
    text = _ask(client, "what did I write about sourdough last week", notes_only=True, use_tools=False)["text"]
    assert "78%" in text and "ready by morning" not in text


def test_a_heading_is_named_without_its_hash():
    from tessellate.ai import composer_frame

    assert composer_frame.short_name({"content": "# Trains\n\nLisbon to Porto, 2h50."}) == "the Trains"


#: "the Porto" was the recorded side until audit 1029 C36: a determiner is not
#: part of the thing named (it headed the side-by-side as "**the Porto**"),
#: and the digest's topic for the same question was already "Porto and Lisbon".
@pytest.mark.parametrize(
    ("ask", "sides"),
    [("compare the Porto and Lisbon notes", ("Porto", "Lisbon")), ("compare Porto notes with Lisbon notes", ("Porto", "Lisbon")), ("Porto vs Lisbon", ("Porto", "Lisbon"))],
)
def test_a_comparison_names_its_two_things_without_the_noun_for_notes(ask, sides):
    assert composer.compare_sides(ask) == sides


def test_reminders_asked_for_a_window_are_that_windows(client, session):
    from datetime import datetime, timedelta

    from tessellate.core.database import Reminder

    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).replace(hour=10, minute=0, second=0, microsecond=0)
    session.add_all([Reminder(text="Water the plants", due_at=monday + timedelta(days=1)), Reminder(text="Book the venue", due_at=monday + timedelta(days=20))])
    session.commit()
    text = _ask(client, "what reminders do I have this week", use_tools=False)["text"]
    assert "Water the plants" in text and "Book the venue" not in text
    assert "this week" in text and "Heads up" not in text


@pytest.mark.parametrize(
    ("ask", "name"),
    [("list my recipes", "recipes"), ("show me my books", "books"), ("what recipes do I have", "recipes"), ("list my reminders", None), ("list my tags", None), ("what tasks do I have", None)],
)
def test_a_bare_plural_names_a_filing_unless_the_app_has_its_own_list(ask, name):
    from tessellate.ai import filed_name

    assert filed_name.filed_listing(ask) == name


def test_ask_lists_a_tag_by_its_plural(client, session):
    from tessellate.entry import manager as m

    m.create_entry(session, "# Chickpea curry\n\nOne tin, one onion.", tags=["recipes"])
    m.create_entry(session, "# Pizza night\n\nHot oven.", tags=["recipes"])
    m.create_entry(session, "# Dentist\n\nCheck-up on the 21st.")
    session.commit()
    text = _ask(client, "list my recipes", notes_only=True, use_tools=False)["text"]
    assert "Chickpea curry" in text and "Pizza night" in text and "Dentist" not in text


def test_search_finds_a_note_by_the_irregular_plural(client, session):
    from tessellate.entry import manager as m

    m.create_entry(session, "# Knife sharpening\n\nWhetstone at 15 degrees, 1000 then 6000 grit.")
    m.create_entry(session, "# Dentist\n\nCheck-up on the 21st.")
    session.commit()
    text = _ask(client, "find notes about knives", use_tools=False)["text"]
    assert "Knife sharpening" in text and "Nothing matched" not in text


def test_a_future_window_with_a_subject_does_not_filter_by_the_day_a_note_was_written():
    from datetime import date

    from tessellate.search import query

    asked = query.understand("my running plan for next month", date(2026, 10, 19))
    assert asked.since is None and asked.until is None and "running" in asked.subject
    past = query.understand("my running plan last month", date(2026, 10, 19))
    assert past.since is not None


@pytest.mark.parametrize("ask", ["delete everything", "wipe all my notes", "please delete all notes"])
def test_a_request_to_delete_everything_is_answered_with_the_safe_way(client, session, ask):
    from tessellate.entry import manager as m

    m.create_entry(session, "# Trip budget\n\nEverything else is mid-range.")
    session.commit()
    text = _ask(client, ask, use_tools=True)["text"]
    assert "Confirm" in text and "Everything else" not in text


@pytest.mark.parametrize(
    ("ask", "words"),
    [("can I use this offline?", "works offline: Tessellate runs on this computer"), ("what does Atlas do", "assistant inside Tessellate"), ("is atlas an assistant, who is atlas", "assistant inside Tessellate")],
)
def test_the_guide_answers_what_the_question_asks_not_a_neighbouring_topic(ask, words):
    from tessellate.ai import help_chat

    out = help_chat.offline_answer(ask, "dashboard", None)
    assert words in " ".join(out["content"].split())


@pytest.mark.parametrize(
    ("ask", "topic"),
    [("compare the Porto and Lisbon notes", "Porto and Lisbon"), ("what is my running plan for next month", "running plan"), ("what did I write about sourdough last week", "sourdough")],
)
def test_the_topic_a_reply_names_is_the_subject_not_a_time_or_a_lowercased_pair(ask, topic):
    from tessellate.ai import composer_digest

    assert composer_digest._topic(ask, []) == topic


def test_one_note_shown_of_many_is_not_called_the_first_ones():
    from tessellate.ai import tool_say

    note = {"id": 1, "title": "Knife sharpening", "content": "# Knife sharpening\n\nWhetstone."}
    lead, _rows, _chips = tool_say._found_notes("I found five notes about “knives”.", [note], 5, "none")
    assert "Here is the closest one." in lead and "the first one" not in lead.replace("Here is the closest one", "")
