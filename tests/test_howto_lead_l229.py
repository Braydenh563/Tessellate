"""L229: a bare how-to leads with the topic's step sentence, never a long inventory of the whole page."""

from __future__ import annotations

import pytest

from tessellate.ai import composer, composer_help, help_chat


def _lead(question: str, tab: str = "dashboard") -> str:
    line, _topic = composer.help_line(question, help_chat.topics_for(question, tab))
    return line


def test_how_do_i_change_the_widgets_leads_with_the_step():
    line = _lead("How do I change the widgets?")
    assert "Widgets" in line and "Edit layout" in line and len(line.split()) <= 40


@pytest.mark.parametrize("question", ["How do I see what changed?", "how do I see my streak", "how do I see the week digest"])
def test_a_long_opening_inventory_does_not_win_the_first_line_prior(question):
    assert len(_lead(question).split()) <= composer_help._HELP_LEAD_WORDS


def test_the_prior_only_goes_to_a_line_short_enough_to_lead():
    short, long = "Press Customise.", " ".join(["word"] * 61) + "."
    assert composer_help._opens_the_how_to(short, [short, long], True)
    assert not composer_help._opens_the_how_to(long, [long, short], True)
    assert not composer_help._opens_the_how_to(short, [long, short], True)
