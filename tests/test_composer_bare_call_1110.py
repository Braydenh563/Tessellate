"""G10 (g1014-1110): "call mum on sunday about christmas plans" is "remind me to call mum on sunday
about christmas plans" (a reminder on that day, with every word of the task), not "I am not sure
I can do that"."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.mark.parametrize("said, task", [
    ("call mum on sunday about christmas plans", "call mum about christmas plans"),
    ("call Anna tomorrow at 5pm about the invoice", "call Anna about the invoice"),
    ("ring the dentist on friday", "ring the dentist"),
])
def test_a_call_with_a_day_is_a_reminder_with_every_word_of_the_task(said, task):
    found = commands.read(said, NOW)
    assert found and found["intent"] == "reminder", found
    assert found["text"].lower().startswith(task.split(" ")[0]) and all(w in found["text"].lower() for w in task.lower().split()), found
    assert found.get("due_at") is not None, found


def test_a_call_about_something_with_no_day_asks_when():
    found = commands.read("call mum about christmas plans", NOW)
    assert found and found["intent"] == "reminder" and not found.get("time_given") and "christmas plans" in found["text"].lower(), found


@pytest.mark.parametrize("said", ["call me back tomorrow", "call it a day", "text me later", "call of duty on friday"])
def test_a_call_that_names_no_one_is_no_reminder(said):
    found = commands.read(said, NOW)
    assert not found or found["intent"] != "reminder", found
