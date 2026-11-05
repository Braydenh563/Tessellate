"""The composed answer names a note once, by its title, and speaks its content (INBOX 741).

The owner, 2026-10-06, verbatim: "rn the ask chat messages just say, ur note
starting with this says this. also ur not starting with this says this,
furthermore, ur note starting with this says this." Every sentence came in
under its note's opening words and "says:". Now the sentence comes first,
the note is named after it as a citation, once, by its heading or, with no
heading, by the day it was written; joiners are varied and never repeated.
"""

from __future__ import annotations

import re

from tessellate.ai import composer
from tessellate.ai import composer_quote
from tests.test_composer_688 import _note, assert_traceable, TODAY

UNTITLED = [
    _note(1, "We booked the hotel in Lisbon for the first week of May. The room has a balcony.", 6),
    _note(2, "The hotel in Lisbon is a short walk from the Alfama trams.", 4),
    _note(3, "Lisbon hotel deposit paid, the rest is due on arrival.", 2),
]


def ask(question: str, notes) -> dict:
    result = composer.compose(question, notes, today=TODAY)
    assert_traceable(result, question, notes)
    return result


def test_an_untitled_note_is_never_named_by_its_first_words():
    result = ask("What about the Lisbon hotel?", UNTITLED)
    text = result["text"]
    #: Its words are quoted once, as the content, never used as its name.
    assert not [p for p in result["parts"] if p[0] == "title"]
    for note in UNTITLED:
        assert text.count(" ".join(note["content"].split()[:4])) <= 1
    assert "**" not in text
    assert not re.search(r"\b(?:says|said): ", text)
    assert "[your note, " in text


def test_no_pile_of_also_or_furthermore():
    text = ask("What about the Lisbon hotel?", UNTITLED)["text"].lower()
    assert "furthermore" not in text and "also says" not in text and "also, in" not in text


def test_a_titled_note_is_named_once_after_its_sentence():
    notes = [
        _note(1, "# Lisbon trip\n\nThe hotel is booked for May. The room has a balcony over the square.", 5),
        _note(2, "# Budget\n\nThe hotel costs 140 a night, breakfast included.", 3),
    ]
    text = ask("What about the hotel?", notes)["text"]
    assert text.count("**Lisbon trip**") == 1 and text.count("**Budget**") == 1
    assert "[**Lisbon trip**]" in text
    #: The content comes before the name, not after "Your note ... says".
    assert text.index("hotel is booked for May") < text.index("**Lisbon trip**")


def test_a_lowered_quote_after_a_joiner_is_still_the_notes_own_words():
    """"Separately, the hills are steep": only words that are never a name
    have their first letter lowered."""
    s = composer.Sentence(1, 0, 0, 10, "The hills are steep.", ["hill"])
    assert composer_quote._lowered(s) == "the hills are steep."
    for kept in ("Lisbon is hilly.", "I booked it.", "Harbor ships soon.", "TODO list done."):
        assert composer_quote._lowered(composer.Sentence(1, 0, 0, 10, kept, ["x"])) is None


def test_the_eval_has_no_note_says_and_no_lead_in_twice():
    from tests import _composer_eval as ev

    rows = ev.run()
    summary = ev.summary(rows)
    assert summary["grounded"] == 1.0
    assert summary["says_colon"] == 0
    assert summary["lead_in_repeats"] == 0
