"""R9-1, R9-2 and R9-3 (composer audit round 9): the sentence an answer leads with is the one
that answers, the note about the subject leads, and a follow-on chip names a noun phrase.
Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)

    def run(question):
        text, events = go(question)
        chips = []
        for e in events:
            chips = e.get("next") or chips
        return text, chips

    return run


@pytest.mark.parametrize(("question", "lead"), [
    ("how do I feed the starter", "Feed it daily with 50 g flour and 50 g water"),
    ("how long was my last run", "You ran 12 km on 8 November"),
    ("what did hannah think of klara and the sun", "Hannah loved it"),
    ("who loved Klara and the Sun", "Hannah loved it"),
    ("what is Doug", "Your sourdough starter is called Doug"),
])
def test_the_answer_leads_with_the_sentence_that_holds_the_ask(ask, question, lead):  # R9-2, R9-3
    assert ask(question)[0].lstrip().startswith(lead), ask(question)[0]


def test_the_where_reader_quotes_the_head_noun_sentence(ask):  # R9-2
    assert "It reads: The password is on the card" in ask("where did i put the wifi password")[0]


def test_a_note_that_holds_the_subject_in_a_short_line_says_that_line(ask):  # R9-2
    text = ask("what have I written about meditation")[0]
    assert "skipped meditation" in text.lower() and "Q4 draft outline" not in text


def test_the_note_about_the_kitchen_leads_not_a_kitchen_drawer(ask):  # R9-3
    text = ask("what do I know about the kitchen")[0]
    assert text.index("Marek") < text.index("kitchen drawer")
    assert ask("what's going on with the kitchen")[0].startswith("Budget £8,000")


@pytest.mark.parametrize("question", [
    "what's the plumber's number", "what's going on with the kitchen", "what did hannah think of klara and the sun",
    "where does she live", "what is Hannah allergic to", "jr pass", "car insurance due", "summary of the Q4 report",
])
def test_a_chip_names_a_noun_phrase_or_is_not_made(ask, question):  # R9-1
    for chip in ask(question)[1]:
        if chip.startswith("Open"):
            continue
        subject = chip.rstrip("?").split(" about ")[-1].split(" on ")[-1]
        low = subject.lower()
        assert not low.startswith(("with ", "the latest")) and "'s" not in low and "allergic" not in low, chip
        assert "klara sun" not in low and "she live" not in low and "insurance due" not in low, chip


def test_a_chip_keeps_a_names_capitals(ask):  # R9-1
    assert any("Japan" in chip for chip in ask("Japan")[1])
