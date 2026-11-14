"""L195: each Guide topic answers the question its own title asks.

The Guide's offline path was run once per topic (246) with the topic's title as
the question and the lead line read. 51 titles reached some other topic first
(or none: "Asking and chatting" read as a greeting); a title now names its
topic outright, with or without "Tell me about".
"""

from __future__ import annotations

import pytest

from tessellate.ai import composer, help_chat
from tessellate.ai.help_topics_more import TOPIC_META

IDS = [topic["id"] for topic in help_chat.HELP_TOPICS]


@pytest.mark.parametrize("topic_id", IDS)
def test_a_topics_title_asked_as_a_question_reaches_that_topic_first(topic_id):
    title = TOPIC_META[topic_id]["title"]
    for question in (title, f"{title}?", f"Tell me about {title.lower()}"):
        got = help_chat.topics_for(question)
        assert got and got[0]["id"] == topic_id, (question, [t["id"] for t in got[:3]])


@pytest.mark.parametrize("topic_id", IDS)
def test_and_the_lead_line_comes_from_it(topic_id):
    title = TOPIC_META[topic_id]["title"]
    line = composer.help_line(title, help_chat.topics_for(title))
    assert line and line[1] == topic_id and line[0].strip(), title


def test_two_topics_never_share_a_title():
    titles = [TOPIC_META[i]["title"].lower() for i in IDS]
    assert len(titles) == len(set(titles))


#: What a lead may not open on: a word that points back at something the line never says.
DANGLING = ("Then ", "Once ", "They ", "It ", "To ", "Also ", "In Trace", "A moved ", "Any other ", "Its ", "These ")


@pytest.mark.parametrize("topic_id", IDS)
def test_the_lead_for_a_title_is_a_sentence_that_stands_alone(topic_id):
    title = TOPIC_META[topic_id]["title"]
    line, _ = composer.help_line(title, help_chat.topics_for(title))
    assert len(line.split()) >= 5, (topic_id, line)
    assert not line.startswith(DANGLING), (topic_id, line)
    assert len(line.split()) <= 60, (topic_id, line)
