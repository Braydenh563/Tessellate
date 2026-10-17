"""Every read tool run for real on a small notebook, then said (BACKLOG "Tool
results are always readable", next step): the answer names the counts,
titles or dates the result holds, never its keys. The needle path ends a turn
with exactly these sentences, so this is what Chat says with no model.
Measured 2026-10-17 before the fix: summarize_notes said "In the all time you
wrote four notes", and search_help said "The help has nothing on that" for
"reminder", a topic the help has."""

from __future__ import annotations

import re

import pytest

from tessellate.ai import tool_say, tools
from tessellate.entry import manager

NOTES = (
    ("Dentist appointment on Tuesday at 3pm with Dr Patel", []),
    ("Golf practice after work, hit some balls at the range", ["golf"]),
    ("University: COMP2001 assignment due 20 October, databases and SQL joins", []),
    ("Golf lesson booked with the club pro on Saturday", ["golf"]),
)

#: tool, its arguments, and words the answer must say.
READS = (
    ("search_notes", {"query": "dentist"}, ("one note", "Dentist appointment")),
    ("list_notes", {"limit": 5}, ("four", "Golf lesson booked")),
    ("count_notes", {"tag": "golf"}, ("two",)),
    ("get_note", {"note_id": 1}, ("Dentist appointment", "Life")),
    ("summarize_notes", {}, ("four notes", "Life")),
    ("summarize_notes", {"days": 7}, ("last 7 days", "four notes")),
    ("notebook_overview", {}, ("four notes", "#golf")),
    ("notebook_structure", {}, ("four notes",)),
    ("list_categories", {}, ("one category", "Life")),
    ("list_tags", {}, ("one tag", "golf")),
    ("search_help", {"query": "reminder"}, ("on reminders", "Reminders tab")),
    ("search_help", {"query": "how do I add a reminder"}, ("Magic add",)),
    ("search_help", {"query": "how do I export my notes"}, ("Export your data",)),
    ("get_current_time", {}, ("It is",)),
    #: O10 (BACKLOG "A tool to list the tools"): the model can look itself up.
    ("list_skills", {"tools": True}, ("tools", "Search notes", "asks first")),

    ("list_skills", {"tool": "set_reminder"}, ("Set reminder is one of my tools", "It takes text", "needs")),
    ("calculate", {"question": "12 * 7"}, ("84",)),
)


@pytest.fixture()
def notebook(session):
    for text, tags in NOTES:
        manager.create_entry(session, text, "Life", tags)
    session.commit()
    return session


@pytest.mark.parametrize(("name", "args", "said"), READS, ids=[f"{r[0]}-{i}" for i, r in enumerate(READS)])
def test_a_real_result_is_said_with_what_it_holds(notebook, name, args, said):
    result = tools.execute_tool(notebook, name, args)
    assert "error" not in result, result
    text = tool_say.say(name, result, args)["text"]
    for words in said:
        assert words in text, (name, words, text)
    assert "{" not in text and "'" + "id'" not in text, text
    assert not re.search(r"\bthe all time\b|\bin all time\b", text, re.I), text
    assert "None" not in text and "nan" not in text.split(), text
