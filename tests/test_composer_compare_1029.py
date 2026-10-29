"""A question that names two sides is answered side by side (audit 1029 C36).

"compare my running notes and my baking notes" has the "<topic> notes" frame
the topic overview takes, so it was answered as an overview of one topic:
"Your notebook holds two notes about compare my running notes and my baking."
A comparison with two sides now goes to the side-by-side answer whatever the
frame, as the digest already does (`composer_digest._kind_if_mine`). Several
phrasings and subjects, Ask and Chat, no model.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import pytest

from tests.test_composer_subject_1029 import D, MODES, notebook  # noqa: F401

NOTES = [
    ("Running log: 5 km on Sunday, 8 km on Tuesday, legs felt heavy.", D(2026, 10, 25, 9)),
    ("Baking notes: sourdough at 230 degrees, rye loaf needs more water.", D(2026, 10, 26, 9)),
    ("Porto trip: the Ribeira at dusk, port cellars across the river.", D(2026, 10, 20, 9)),
    ("Lisbon trip: trams up to Alfama, custard tarts in Belem.", D(2026, 10, 21, 9)),
]
SIDES = [("running", "baking", "Running log", "Baking notes"), ("Porto", "Lisbon", "Porto trip", "Lisbon trip")]
FRAMES = [
    "compare my {a} notes and my {b} notes",
    "compare {a} and {b}",
    "compare my {a} and {b} notes",
    "compare the {a} notes with the {b} notes",
]


@MODES
@pytest.mark.parametrize("frame", FRAMES)
@pytest.mark.parametrize("side", SIDES, ids=["running-baking", "porto-lisbon"])
def test_two_sides_are_answered_side_by_side(notebook, chat, frame, side):  # noqa: F811
    a, b, note_a, note_b = side
    go = notebook(NOTES)
    text = go(frame.format(a=a, b=b), chat=chat)
    # Each side under its own heading, each with its own note.
    assert f"**{a}**" in text.replace(f"**{a.lower()}**", f"**{a}**"), text
    assert f"**{b}**" in text.replace(f"**{b.lower()}**", f"**{b}**"), text
    assert text.index(note_a) < text.index(note_b), text
    # Never an overview whose topic is the question's own words.
    assert "notes about compare" not in text and "about compare" not in text, text
