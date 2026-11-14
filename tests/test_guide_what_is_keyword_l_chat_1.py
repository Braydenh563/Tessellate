"""L-chat-1 (INBOX 904 B86, "the composer guide didn't answer my question"):
"what is X" where X is a topic's own keyword answers from that topic. Measured
over every topic's first two keywords asked three ways from an unrelated tab
(1,452 questions), seven "what is" forms got "I don't have help on that"
though the keyword is the topic's: the subject rule read only titles and
bodies."""

from __future__ import annotations

import pytest

from tessellate.ai import help_chat

MISSES = "I don't have help on that"


@pytest.mark.parametrize(("question", "topic"), [
    ("what is note history", "note-history"), ("what is memory map", "name"), ("what is atlas look", "atlas-look"),
    ("what is atlas style", "atlas-look"), ("what is choose a model", "chat-model-picker"), ("what is cant find", "find-a-place"),
])
def test_what_is_a_topics_own_keyword_answers_from_it(app_state, question, topic):
    reply = help_chat.offline_answer(question, "graph", "Graph: how your notes connect.")
    assert not reply["content"].startswith(MISSES), reply["content"][:120]
    assert reply["sources"] and reply["sources"][0] == topic.replace("-", " ").capitalize(), reply["sources"]


def test_every_topics_keywords_get_an_answer_from_another_tab(app_state):
    """The sweep the row was measured with: no keyword question is a miss."""
    missed = []
    for topic in help_chat.HELP_TOPICS:
        for keyword in topic["keywords"][:2]:
            for question in (f"how do I use {keyword}", f"where is {keyword}", f"what is {keyword}"):
                said = help_chat.offline_answer(question, "graph", "Graph: how your notes connect.")["content"]
                if said.startswith(MISSES) or said.startswith("Graph: how"):
                    missed.append(question)
    assert not missed, missed
