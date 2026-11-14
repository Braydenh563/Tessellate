"""The no-model coverage gate (L-timeline-9) leaves a note's real answer alone.

Review of the first gate found eight questions over the voice_1110 notebook that
lost their answer: a shared everyday word ("car", "phone", "review", "run") was
what the note was about, or the missing word was a typo of a held one ("agree",
"Agreed"). Each must still get the note's answer, not the general-knowledge reply
or "no mention of".
"""

from __future__ import annotations

import pytest

from tessellate.ai.composer_empty import stray_match
from tessellate.ai.composer_read import read_note
from tests.test_composer_route_688 import _ask
from tests.test_phrasing_real_1111 import _fixed_now, notebook  # noqa: F401  (fixtures)


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("how much was the car maintenance", "$420"),
        ("how much was the car repair", "$420"),
        ("what's the phone bill", "Phone 30"),
        ("when is the repair man coming", "thursday between 8 and 10"),
        ("when is the app going live", "14 December"),
        ("what is the jr pass advice", "not worth it under 7 days"),
        ("what was my review score", "exceeds"),
        ("what was my best run time", "5 km in 27:40"),
        ("what did we agree in the meeting", "Agreed to cut the referral feature"),
    ],
)
def test_the_note_that_answers_is_still_quoted(client, notebook, question, answer):  # noqa: F811
    said = _ask(client, question, use_tools=False)["text"]
    assert answer in said, said
    assert "general knowledge" not in said and "no mention of" not in said.lower(), said


def _view(note_id, content, category="", tags=()):
    return read_note({"id": note_id, "content": content, "category": category, "tags": list(tags)}, 0)


def test_a_question_met_only_on_an_everyday_word_is_stray():
    garden = _view(1, "# Garden\n\nWater every second day.", "Home")
    assert stray_match(["day", "off", "request"], [garden]) == ["off", "request"]


def test_a_ledger_row_named_by_the_question_is_not_stray():
    #: "Phone 30." is the budget's row about the phone: the question is answered there.
    budget = _view(2, "# Budget November\n\nRent 650. Groceries 140. Phone 30.", "Money", ["budget"])
    assert stray_match(["phone", "bill"], [budget]) == []


def test_a_note_holding_most_of_the_question_is_not_stray():
    garden = _view(1, "# Garden\n\nWater every second day.", "Home")
    assert stray_match(["day", "water"], [garden]) == []


def test_an_empty_day_lead_names_the_thing_asked():
    # L-timeline-12: "is there a call tomorrow" was told "No meeting is written", naming a word it never asked.
    from tessellate.ai.composer_event_verdict import lead

    assert lead("is there a call tomorrow", "") == "No call is written for tomorrow."
    assert lead("are we meeting on Tuesday", "") == "No meeting is written for Tuesday."
    assert lead("are there interviews on Friday", "") == "No interview is written for Friday."


def test_a_plural_meeting_ask_reads_as_an_event_question():
    # L-timeline-13: plural asks fell through the event reader and lost their verdict.
    from tessellate.ai.composer_event_verdict import lead
    from tessellate.ai.recognise_questions import event_window_asked

    assert event_window_asked("do i have calls tomorrow") == "tomorrow"
    assert event_window_asked("are there interviews on Friday") == "on Friday"
    assert event_window_asked("do I have any classes this week") == "this week"
    assert lead("are there interviews on Friday", "") == "No interview is written for Friday."


def test_a_to_do_add_said_verb_last_adds_the_task():
    # L-timeline-10: "on my to do list, i need cleaning added" fell through to a search and quoted a note on "clean".
    from datetime import datetime

    from tessellate.ai import commands

    now = datetime(2026, 11, 14, 9)
    for said in ("on my to do list, i need cleaning added", "i need cleaning added to my to do list"):
        found = commands.read(said, now)
        assert found and found["intent"] == "reminder" and found["task"], said
        assert found["text"] == "Cleaning" and found["on_list"] == "cleaning" and found["asked"] == said, found
