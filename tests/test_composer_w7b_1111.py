"""W7b composer rows (2026-11-11): B7 a subject's own name, B7b "want to read", B10 a verb is not the plural noun,
B33 a proper noun in a quoted line, B34 a joke note leads by its joke. Fixed clocks only (the seeds')."""

from __future__ import annotations

import pytest

import tests._seed_bt_1109 as bt
import tests._seed_r2_1107 as r2
import tests._seed_r9_1109 as r9
from tessellate.ai import composer_verbuse


@pytest.fixture
def go(client, session, monkeypatch):
    r9.seed(session)
    return r9.asker(client, monkeypatch)


# --- B7: the newest note about a subject, found by the name the person's notes give it ---------------------------
@pytest.mark.parametrize("ask", [
    "what's the latest on sourdough", "latest on sourdough", "what's new with the sourdough", "the newest on my sourdough",
    "any news on sourdough",
])
def test_latest_on_a_subject_leads_the_newest_note_by_its_given_name(go, ask):
    text = go(ask)[0]
    assert text.startswith("Doug the starter is bubbly again"), text


# --- B7b: "want", "plan", "would like" reach the same list as "need" --------------------------------------------
@pytest.mark.parametrize("ask", [
    "what do I need to read", "what do I want to read", "what would I like to read", "what do I plan to read",
])
def test_the_reading_list_answers_every_wish_verb(go, ask):
    text = go(ask)[0]
    assert text.startswith("Three to read, from your Reading note"), text
    assert "- [ ] Piranesi" in text, text


def test_a_wish_for_something_else_does_not_open_the_reading_list(go):
    assert "Three to read" not in go("what do I want to eat")[0]


# --- B10: "book the X" is the verb, not the books ----------------------------------------------------------------
@pytest.mark.parametrize("ask", ["what do I know about books", "tell me about books", "what do I have on books"])
def test_books_are_not_the_verb_to_book(go, ask):
    text = go(ask)[0]
    assert "book car service" not in text.lower(), text
    assert "Book club meets" in text, text


@pytest.mark.parametrize("text,expect", [
    ("You need to book the tram for Friday.", True),
    ("Book the dentist.", True),
    ("- [ ] book car service", True),
    ("Please book it, then pay.", True),
    ("Book club meets on Tuesday.", False),
    ("Her books are on the shelf.", False),
    ("Three books to read.", False),
    ("Nothing about it.", False),
])
def test_only_a_verb_reads_the_word_as_a_verb(text, expect):
    assert composer_verbuse.only_a_verb("books", text) is expect


def test_a_singular_subject_keeps_the_verb_notes():
    assert composer_verbuse.only_a_verb("book", "Book the dentist.") is False


def test_a_note_with_a_second_word_of_the_question_stays():
    scored = [(2, "tram"), (1, "club")]
    kept = composer_verbuse.drop(["books", "tram"], scored, lambda v: "You need to book the tram" if v == "tram" else "Book club meets")
    assert kept == scored


# --- B33: a proper noun keeps its capital in a quoted line ------------------------------------------------------------
@pytest.mark.parametrize("ask", ["what's on the agenda for the team sync", "what is on the agenda with Priya"])
def test_a_proper_noun_keeps_its_capital_in_a_line_quoted_from_a_note(client, session, monkeypatch, ask):
    bt.seed(session)
    r9.fix_clock(monkeypatch)
    text = r9.ask(client, ask, notes_only=True)["text"]
    assert "Orchard project budget" in text, text
    assert "orchard project" not in text, text


# --- B34: the joke leads by its joke, whole, never by "Jokes was outstanding" ---------------------------------------------
@pytest.mark.parametrize("ask", ["tell me a joke", "what jokes do I have", "do I have a joke", "what do I know about jokes"])
def test_a_joke_note_leads_by_its_question_and_its_punchline(ask):
    text = r2.ask(ask)
    assert "Why did the scarecrow win an award? He was outstanding in his field." in text, text
    assert "Jokes was" not in text, text
    assert "**Also:**" not in text, text
