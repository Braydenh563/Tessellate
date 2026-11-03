"""Audit 1028 E27: an act's line starts a sentence with a capital."""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer_compose as compose
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


# --- E27: an act's line starts a sentence with a capital -----------------------------


@pytest.mark.parametrize("voice", ["natural", "plain", "playful", "professional"])
@pytest.mark.parametrize("ability", ["act_done", "act_card"])
def test_an_act_line_never_starts_a_sentence_in_lower_case(voice, ability):
    for seed in range(40):
        mood = compose.mood_of("make a note", voice=voice, seed=str(seed), intent="act")
        said = compose.frame(ability, mood, what="created “Shopping list” in Uncategorised")
        for start in re.finditer(r"(?:^|[.!?]\s)(\S)", said):
            assert not start.group(1).islower(), said


def test_a_filled_frame_keeps_the_what_lower_where_it_follows_a_word():
    said = {compose.frame("act_done", compose.mood_of("x", voice="warm", seed=str(s)), what="added to Favourites: “Budget”") for s in range(40)}
    assert any(s.startswith("Done: added to") or s.startswith("I have added") for s in said), said


def test_an_act_run_through_chat_is_sentence_case_with_no_id_and_no_stale_notice(client, session):
    manager.create_entry(session, "# Budget\n\nRent is 650 a month.", category_name="Personal")
    session.commit()
    for question in ("create a note called Shopping list", "make a note: buy milk", "pin the budget note"):
        events = _ask(client, question, use_tools=False)
        card = events["act"][0]
        assert card["done"] is True and card["notice"] == "", question
        assert not re.search(r"#\d", card["summary"]), card["summary"]
        assert card["summary"][0].isupper(), card["summary"]


