"""Audit 1028 E20: a weekday word in a log note is a day gone, not a day due.

"Wednesday bench 60kg." in a gym log was listed under Today and Friday as a
due item. The class: a line that names its day by a bare weekday and records
what was done on it (a measured result, or any line of a log, diary or
tracker). A plan, schedule or routine note keeps its weekdays as arranged.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import composer_plan
from tessellate.ai import recognise_questions

NOW = datetime(2026, 11, 2, 12, 0)


@pytest.mark.parametrize(
    ("sentence", "title"),
    [
        ("Wednesday bench 60kg for 5 reps.", "Gym log"),
        ("Friday deadlift 100kg.", ""),
        ("Tuesday ran 5 km before work.", "Running diary"),
        ("Monday 3 sets of 10 reps.", "Workout notes"),
        ("Thursday: slept badly, tired all day.", "Sleep tracker"),
        ("Saturday squat 3x5 at 90 lbs.", ""),
        ("Sunday long run, 12 miles.", "Training journal"),
    ],
)
def test_a_measured_or_logged_weekday_is_a_day_gone(sentence, title):
    assert recognise_questions.logged_day(sentence, title), (sentence, title)


@pytest.mark.parametrize(
    ("sentence", "title"),
    [
        ("Friday: past papers and flashcards.", "Study plan"),
        ("Monday: biology chapters 4 and 5.", "Study plan"),
        ("Dentist on Friday at 3pm.", "Appointments"),
        ("The essay is due Friday.", "Gym log"),
        ("Friday deadlift 100kg, booked for the gym.", ""),
        ("Next Monday squat 80kg.", ""),
        ("Monday 5 km run.", "Training plan"),
        ("Wednesday bench 60kg on 11 November.", "Gym log"),
        ("Call Sara on Friday.", "Odds and ends"),
    ],
)
def test_a_planned_or_deadlined_weekday_stays_a_day_ahead(sentence, title):
    assert not recognise_questions.logged_day(sentence, title), (sentence, title)


def _days(content: str) -> list[str]:
    note = {"id": 1, "content": content, "created_at": datetime(2026, 10, 28, 9, 0)}
    return [text for _, text in composer_plan._note_days(note, NOW)]  # noqa: SLF001


def test_a_gym_log_lists_no_due_item():
    log = "# Gym log\n\nMonday squat 80kg for 5 reps.\nWednesday bench 60kg for 5 reps.\nFriday deadlift 100kg for 3 reps.\n"
    assert _days(log) == []


def test_a_plan_beside_a_log_line_keeps_the_plan():
    plan = "# Week plan\n\nFriday: hand in the essay.\nMonday squat 80kg for 5 reps.\n"
    #: A plan note keeps its weekdays as arranged, a measure on one included.
    assert any("essay" in line for line in _days(plan))
    assert any("squat" in line for line in _days(plan))
