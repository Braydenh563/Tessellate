"""Audit 1028 E55: a tag act that names a note and no tag asks which tag."""

from __future__ import annotations


import pytest

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def _said(client, question):
    return _ask(client, question, use_tools=False)["text"]


# --- E55: a tag act that names a note and no tag asks which tag ------------------------


@pytest.fixture
def tagged(session):
    manager.create_entry(session, "# Gym log\n\nNeeds a new plan.", category_name="Health", tags=["fitness", "plan"])
    manager.create_entry(session, "# Budget\n\nRent is 650 a month.", category_name="Personal")
    session.commit()


@pytest.mark.parametrize("question", ["untag my gym note", "untag the gym note", "please untag my gym log", "can you untag the gym note"])
def test_untag_with_no_tag_asks_which_tag_and_names_the_notes_tags(client, tagged, question):
    said = _said(client, question)
    assert said.startswith("Which tag"), said
    assert "#fitness" in said and "#plan" in said, said
    assert "I don't see any mention" not in said and "Needs a new plan" not in said


def test_untag_on_a_note_with_no_tags_says_so(client, tagged):
    said = _said(client, "untag my budget note")
    assert "no tags" in said and "Which tag" not in said, said


def test_tag_with_no_tag_asks_which_tag(client, tagged):
    said = _said(client, "tag my gym note")
    assert said.startswith("Which tag"), said


