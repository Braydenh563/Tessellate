"""Composer round 5, 2026-11-08 (counts): rows of audits 1107 (D, E, R3) that round 4 left unfixed. Every
question runs through `/chat/stream` with no model and a fixed clock, because the seams these
rows share (the pool the route builds, the act cues, the history) sit in front of the composer."""

from __future__ import annotations

import time

import pytest

from tests import _r5_1108 as r5



@pytest.fixture
def ask(client, session, monkeypatch):
    return r5.driver(client, session, monkeypatch)


@pytest.mark.parametrize("question", ["number of notes about Sara", "how many notes about Sara", "the number of notes about Sara", "count notes about Sara", "count my notes on Sara"])
def test_r3_6_every_count_phrasing_gives_the_subjects_real_count(ask, question):
    said = ask(question)["text"]
    assert said.startswith("You have seven notes about Sara."), said


def test_r3_6_count_notes_about_the_dentist_is_the_dentists_count(ask):
    said = ask("count notes about the dentist")["text"]
    assert said.startswith("You have three notes about the Dentist."), said
    assert "32" not in said, said


def test_d4_words_in_the_longest_note_is_that_notes_length(ask):
    said = ask("how many words in my longest note")["text"]
    assert said.startswith("Your longest note is") and "words" in said and "You have" not in said, said


def test_count_with_no_subject_is_still_the_notebook_total(ask):
    assert ask("count my notes")["text"].startswith("You have 32 notes"), ask("count my notes")


def test_r3_6_the_new_count_opener_is_linear():
    from tessellate.ai import composer_overview

    for run in ("number of notes about " + "a " * 5000, "count " * 2000 + "notes about x", "the number of " * 800, "total notes on " + " " * 9000):
        t0 = time.perf_counter()
        composer_overview.topic(run)
        assert time.perf_counter() - t0 < 1.0, run[:30]
