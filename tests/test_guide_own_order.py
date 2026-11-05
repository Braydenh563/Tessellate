"""Ordering a list reaches the card-drag topic, not filing (blindux 1031 I5).

"put my notes in my own order" read as the hard move-note row and answered
with Tags and categories; the class is any ask to order or rearrange a list.
"""

import pytest

from tessellate.ai import help_chat

ORDER = (
    "How do I put my notes in my own order?",
    "put my notes in my own order",
    "reorder my notes",
    "rearrange my documents",
    "sort notes in a custom order",
    "how do I put my notes in order",
    "put notes in alphabetical order",
    "get my documents in the right order",
)
FILING = (
    "move my note to the work category",
    "put this note in the Recipes category",
    "file my notes",
    "move a note to another space",
    "I want to move notes in order to tidy up",
)
#: Arranging a surface is that surface's topic, not a list's order.
SURFACE = (("can I rearrange my dashboard", "dashboard"),)


@pytest.mark.parametrize("question", ORDER)
def test_an_ask_to_order_a_list_leads_with_the_card_drag(question):
    assert help_chat.topics_for(question)[0]["id"] == "object-move"


@pytest.mark.parametrize("question", FILING)
def test_filing_a_note_still_leads_with_tags_and_categories(question):
    assert help_chat.topics_for(question)[0]["id"] == "tags-categories"


@pytest.mark.parametrize(("question", "topic"), SURFACE)
def test_arranging_a_surface_keeps_its_own_topic(question, topic):
    assert help_chat.topics_for(question)[0]["id"] == topic
