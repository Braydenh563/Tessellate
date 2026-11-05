"""Audit 1028 E23: a quiz question must not cut the subject off.

'Which term means: "on 12 November, covers chapters 4 to 6"?' came from "The
exam is on 12 November, covers chapters 4 to 6": a sentence whose verb is
followed by a time, a place, a price or a state, not by what the thing is. The
class: only a body that names a kind of thing (a noun phrase, "the process
by which ...", "how plants ...") is turned round into a question or answer;
any other sentence makes no define or term card, and the section's own
"what do your notes say about" card is left to ask about it.
"""

from __future__ import annotations

import pytest

from tessellate.ai import study


def _cards(sentence: str, title: str = "Biology") -> list:
    return study.cards(f"# {title}\n\n{sentence}\n")


@pytest.mark.parametrize(
    "sentence",
    [
        "The exam is on 12 November, covers chapters 4 to 6.",
        "The essay is due on Friday and counts for 30 percent.",
        "Glycolysis is in the cytoplasm.",
        "The lecture is at 9am in room 4.",
        "The deadline is 6 November.",
        "Revision is going well.",
        "The final is worth 40 percent of the grade.",
        "The meeting is with Sara about the project plan.",
        "The seminar is next Tuesday afternoon in the library.",
        "The practical is confirmed for the second week of term.",
        "The library is open until ten tonight.",
        "Chapter four is important for the exam and the quiz.",
        "The labs are on Mondays and Thursdays this term.",
        "The report is about the effect of heat on enzymes.",
    ],
)
def test_a_sentence_about_when_where_or_how_much_makes_no_term_card(sentence):
    cards = _cards(sentence)
    assert not [c for c in cards if c.kind in ("define", "term")], [(c.kind, c.q, c.a) for c in cards]


@pytest.mark.parametrize(
    ("sentence", "term"),
    [
        ("Mitosis is the process by which a cell divides into two identical cells.", "Mitosis"),
        ("The mitochondria are the organelles that make most of the cell's ATP.", "mitochondria"),
        ("Photosynthesis is how plants turn light into chemical energy.", "Photosynthesis"),
        ("Osmosis is a type of diffusion across a membrane.", "Osmosis"),
        ("An enzyme is a protein that speeds up a reaction.", "enzyme"),
        ("Diffusion is the movement of particles from high to low concentration.", "Diffusion"),
        ("Homeostasis refers to keeping the internal conditions of a body steady.", "Homeostasis"),
    ],
)
def test_a_real_definition_still_makes_both_cards(sentence, term):
    kinds = {c.kind: c for c in _cards(sentence)}
    assert "define" in kinds and "term" in kinds, [(c.kind, c.q) for c in _cards(sentence)]
    assert kinds["term"].a.lower() == term.lower()


@pytest.mark.parametrize(
    "line",
    [
        "- Exam: on 12 November, covers chapters 4 to 6",
        "- Deadline: by Friday at noon",
        "- Lecture: at 9am in room 4",
        "- Venue: in the main hall",
    ],
)
def test_a_labelled_line_of_a_time_or_a_place_makes_no_definition(line):
    cards = _cards(line)
    assert not [c for c in cards if c.kind == "define"], [(c.kind, c.q, c.a) for c in cards]


def test_a_labelled_line_that_names_a_thing_still_does():
    cards = _cards("- **Osmosis**: movement of water across a membrane")
    assert [c for c in cards if c.kind == "define"]
