"""Composer round 5, 2026-11-08 (follow-on): rows of audits 1107 (D, E, R3) that round 4 left unfixed. Every
question runs through `/chat/stream` with no model and a fixed clock, because the seams these
rows share (the pool the route builds, the act cues, the history) sit in front of the composer."""

from __future__ import annotations



import pytest

from tests import _r5_1108 as r5



@pytest.fixture
def ask(client, session, monkeypatch):
    return r5.driver(client, session, monkeypatch)


def test_e5_a_property_only_follow_on_keeps_the_trip(ask):
    said = r5.chain(ask, "tell me about the Tokyo trip", "where is it", "what should I pack", "when does it start")
    assert "Packing for Tokyo" in said[2] and "Lisbon" not in said[2], said[2]
    assert "Tokyo trip" in said[3] and "3 April" in said[3], said[3]


def test_d6_the_dentist_chain_keeps_its_subject(ask):
    said = r5.chain(ask, "what do I know about the dentist", "when is the next appointment", "how much did it cost")
    assert "11 November" in said[1] and "Priya" not in said[1], said[1]
    assert "£85" in said[2] and "none of these" not in said[2].lower(), said[2]


def test_e5_a_property_question_with_its_own_subject_is_not_carried(ask):
    said = r5.chain(ask, "tell me about the Tokyo trip", "what should I pack for Lisbon")
    assert "Packing for Tokyo" not in said[1], said[1]


def test_e23_a_named_date_is_not_read_back_as_its_own_answer(ask):
    said = ask("what day is 14 March")["text"]
    assert said.startswith("That is Sunday 14 March 2027."), said
    assert said.count("14 March") == 2 and "as Sunday" not in said, said


def test_e22_my_landlord_is_your_landlord_in_the_frame(ask):
    said = ask("who is my landlord")["text"]
    assert said.startswith("Your landlord comes up once"), said
    assert "names your landlord" in said and "My landlord" not in said, said


def test_e22_a_name_only_titles_write_keeps_its_capital(ask):
    assert ask("how many notes mention tokyo")["text"].startswith("You have two notes about Tokyo."), ask("how many notes mention tokyo")


def test_d21_a_feature_word_gets_one_short_line_not_a_settings_paragraph(ask):
    #: "what is my name" is the G7 name question now (`ai/address.py`); the feature word is "backup".
    said = ask("backup")["text"]
    assert "one of the app's own tools" in said and len(said.split()) <= 40, said
