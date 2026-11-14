"""L-chat-189 (the owner: "the composer should probably use better md rendering and structuring, quotation
marks, as well as alter personal words used in notes like my or I to you or your"): the answers on the round 9
notebook speak to the person, quote with curly marks, and never show raw Markdown syntax of the notes
(a checklist's `- [ ]` boxes, a heading's `#`, a table's pipes) inside a sentence or a list line."""

from __future__ import annotations

import re

import pytest

import tests._seed_r9_1109 as sd

QUESTIONS = [
    "what did I write last Friday",
    "what did I write about the kitchen",
    "what did I write yesterday",
    "what did I say about mum",
]
RAW = re.compile(r"\[[ xX]\]|^\s*#{1,6}\s|\|\s*---")


@pytest.fixture()
def answers(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    return {q: sd.ask(client, q, notes_only=True)["text"] for q in QUESTIONS}


def test_no_answer_shows_the_notes_raw_markdown(answers):
    for question, text in answers.items():
        assert not RAW.search(text), (question, text)


def test_a_checklist_is_read_out_as_items_not_boxes(answers):
    text = answers["what did I write last Friday"]
    assert "email Raj the draft; book car service" in text, text


def test_the_notes_words_are_quoted_with_curly_marks_and_said_to_you(answers):
    text = answers["what did I write about the kitchen"]
    assert "“" in text and '"' not in text.replace('"]', ""), text
    assert text.count("You ") + text.count("Your ") >= 2, text
    assert not re.search(r"\b(I|my|me)\b", re.sub(r"“[^”]*”", "", text)), text
