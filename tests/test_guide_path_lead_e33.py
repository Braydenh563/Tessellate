"""Audit 1028 E33, the part that needed no decision: a place that starts with
"The" reads as a sentence ("It's in the gear in the top bar", not "It's in The gear").
The path-first order the audit asks for is pinned the other way by
tests/test_guide_composed_787.py, test_guide_social_1414.py and
test_help_chat_reading.py, so it is listed for the owner
(docs/roadmap/agent-remaining/a30e-1102.md)."""

from __future__ import annotations

import pytest

from tessellate.ai import help_chat


@pytest.mark.parametrize("question", ["where are my settings", "where is the settings menu", "where do I find settings"])
def test_a_place_that_starts_with_the_reads_as_a_sentence(question):
    text = help_chat.composed_answer(question, help_chat.topics_for(question))
    assert "It's in The" not in text, text
    assert text.startswith("It's in the gear"), text


@pytest.mark.parametrize(
    ("path", "said"),
    [
        ("Reminders tab", "the Reminders tab"),
        ("The Chat tab, or Ctrl+Shift+A over any tab", "the Chat tab, or Ctrl+Shift+A over any tab"),
        ("The picker at the top of the sidebar", "the picker at the top of the sidebar"),
        ("Settings, Models", "Settings, Models"),
        ("Ctrl+K", "Ctrl+K"),
    ],
)
def test_place_reads_each_shape_of_path(path, said):
    assert help_chat._place(path) == said  # noqa: SLF001
