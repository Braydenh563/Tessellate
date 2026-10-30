"""Composer audit 2026-10-30, classes 1 and 2: a note's words are never spliced
into a frame that changes who they are about, and a derived line is only said
when it is true (docs/roadmap/agent-remaining/audit-1030-composer.md)."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_frame
from tests import _seed_1030 as seed_1030


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    return seed_1030.asker(client, monkeypatch)


def _said(ask, question):
    return ask(question)[0]


@pytest.mark.parametrize("question", ["what do I know about Atlas", "tell me about Priya", "summarise Priya"])
def test_z1_a_first_person_note_is_never_spliced_after_youre(ask, question):
    said = _said(ask, question)
    assert "you're we" not in said and "you're I" not in said, said
    assert "and you're we" not in said, said


@pytest.mark.parametrize(("question", "bad"), [
    ("what have I written about baking", "You jotted down Feed"),
    ("what do I know about sourdough", "You noted Bake"),
    ("tell me about Priya", "You jotted down we"),
    ("what do I know about Atlas", "You wrote down slept"),
    ("what did I write about running", "jotted down Tuesday"),
])
def test_z2_a_note_to_self_or_a_we_is_quoted_or_reported_not_spoken_for_the_writer(ask, question, bad):
    said = _said(ask, question)
    assert bad not in said and bad.lower() not in said.lower(), said


def test_z2_an_imperative_is_quoted_with_its_capital(ask):
    said = _said(ask, "what do I know about sourdough")
    assert "Your note says “Feed the starter" in said, said


@pytest.mark.parametrize("question", ["what do I know about books", "tell me about Tom", "what do I know about the Tokyo trip"])
def test_z5_a_past_event_is_never_months_away(ask, question):
    said = _said(ask, question)
    assert "eleven months" not in said and "eight months" not in said, said


def test_z6_a_gap_is_not_computed_between_unrelated_prices(ask):
    for question in ("what is my budget", "tell me about money", "what do I spend"):
        said = _said(ask, question)
        assert "a gap of" not in said, said


@pytest.mark.parametrize(("question", "kept", "dropped"), [
    ("what do I know about the dentist", "book the dentist", "renew passport"),
    ("what do I know about the passport", "renew passport", "book the dentist"),
    ("tell me about the cloud assignment", "finish the cloud assignment", "renew passport"),
])
def test_z8_a_to_do_rides_only_on_an_answer_about_it(ask, question, kept, dropped):
    said = _said(ask, question)
    assert dropped not in said, said
    assert kept in said, said


def test_z9_the_count_is_the_notes_listed_as_about_it(ask):
    said = _said(ask, "what do I know about books")
    assert said.startswith("You have two notes about books"), said
    assert "More loosely related to books" in said, said


def test_z10_one_word_count_for_longest_and_longer(ask):
    longest = _said(ask, "what is my longest note")
    longer = _said(ask, "which is longer, the Lisbon trip or the Tokyo trip")
    count = composer_frame.note_words(next(c for c, _tags, _days in seed_1030.NOTES if c.startswith("# Lisbon trip")))
    assert f"about {count} words" in longest and f"{count} words against" in longer, (count, longest, longer)


def test_z44_a_snippet_has_no_markup_and_is_cut_at_a_word():
    got = composer_frame.plain_snippet("# Lisbon trip\nFlying out on 14 November 2026 and back on 21 November. Staying at Hotel Alfama.")
    assert got.startswith("Lisbon trip Flying out") and "#" not in got and not got.endswith(" "), got
    assert composer_frame.plain_snippet("- [ ] milk\n- [x] eggs") == "milk eggs"
    assert composer_frame.note_words("# Title\n\n- [ ] one two") == 2
