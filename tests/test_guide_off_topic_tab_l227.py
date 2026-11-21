"""L227: an off-topic Guide question asked from a tab is refused, not answered with that tab's help."""

import pytest

from tessellate.ai import help_chat


@pytest.mark.parametrize("tab", ["notes", "dashboard", "reminders", None])
@pytest.mark.parametrize("question", ["what's the weather today", "who won the football last night"])
def test_an_off_topic_question_says_it_is_outside_the_app(question, tab):
    assert help_chat.topics_for(question, tab) == []
    said = help_chat.offline_answer(question, tab)
    assert "outside the app" in said["content"] and not said["badges"]
