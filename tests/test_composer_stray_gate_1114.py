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
