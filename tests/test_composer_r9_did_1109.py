"""R9-7 (composer audit round 9): did-I and yes/no verdicts. A bare imperative is a plan, not a record;
a note is named by its title; a yes/no that the notes answer starts with the verdict.
Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def test_a_bare_imperative_is_a_plan_not_a_record(say):
    text = say("did I call mum")
    assert not text.startswith("Yes")
    assert text.startswith("Not yet")


def test_bought_in_a_titled_note_answers_yes_by_title(say):
    text = say("did I buy the concert tickets")
    assert text.startswith("Yes")
    assert "Concert" in text and "bought two" in text
    assert "I found nothing" not in text


def test_a_titled_note_is_named_by_its_title(say):
    text = say("have I read Klara and the Sun")
    assert "Book club notes" in text
    assert "your note of 25 October" not in text


def test_the_plumber_this_week_is_read_for_the_event_not_the_writing(say):
    text = say("is the plumber coming this week")
    assert "Wednesday 11 November" in text
    assert "no mention" not in text


def test_do_i_need_to_renew_is_a_yes_from_the_title_only_note(say):
    text = say("do I need to renew my passport")
    assert text.startswith("Yes")
    assert "Renew passport" in text
