"""L241: the Guide's profile topic answers "call me Sam" and "what you call me"."""

import pytest

from tessellate.ai import help_chat


@pytest.mark.parametrize("question", ["call me Sam", "how do I change what you call me", "can you call me by another name", "how do I make Atlas call me Sam"])
def test_a_what_to_call_me_question_reaches_the_profile_topic(question):
    assert [t["id"] for t in help_chat.topics_for(question, "notes")][:1] == ["profile"]


def test_the_profile_topic_says_that_telling_atlas_sets_the_name():
    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "profile")
    assert 'call me Sam' in body and len(body) < 1900
