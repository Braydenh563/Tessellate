"""A named note is not a statistic (notes audit 1031, N32).

"show the note about golf" answered with the tag chart: the stats router took
any sentence with "note ... about X". A subject needs a stats word.
"""

import pytest

from tessellate.ai import notebook_stats


@pytest.fixture
def session_with_notes(client):
    from tessellate.core import deps

    for text in ("harbor launch plan", "recipe for soup", "weekend trip"):
        client.post("/entries", json={"content": text, "tags": ["harbor", "food"]})
    with deps.get_db().session() as session:
        yield session


@pytest.mark.parametrize(
    "question",
    [
        "show the note about golf",
        "find the note about golf",
        "the note about golf",
        "open my note on plumbers",
        "what is in the note about soup",
        "read me the notes that mention golf",
    ],
)
def test_a_named_subject_is_left_to_the_search(session_with_notes, question):
    assert notebook_stats.answer(question, session_with_notes) is None, question


@pytest.mark.parametrize(
    "question",
    ["how many notes do I have", "what are my top tags", "show me my stats", "how many notes about harbor"],
)
def test_a_stats_word_still_answers(session_with_notes, question):
    assert notebook_stats.answer(question, session_with_notes) is not None, question
