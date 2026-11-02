"""The Guide finds a topic by the rare words of a question, not the common one
(INBOX 1530 a): "is there a companion that can show outside of the app on my
desktop?" answered The corner companion because "companion" is a keyword by
itself, while "desktop" and "outside" only appear in the desktop companion's
phrases. `tests/fixtures/guide_paraphrases_1530.json` holds paraphrases (no
topic's exact keyword phrase) for more than ten topics; the class is every
topic, not this one."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from tessellate.ai import help_chat

#: The app module registers the reading and the spelling repair, as the
#: running app has them; imported for that alone.
importlib.import_module("tessellate.api.app")

BANK = json.loads((Path(__file__).parent / "fixtures" / "guide_paraphrases_1530.json").read_text())


def test_bank_covers_ten_topics_with_three_paraphrases_each():
    by_topic: dict[str, int] = {}
    for _, expected in BANK:
        by_topic[expected] = by_topic.get(expected, 0) + 1
    assert len(by_topic) >= 10
    assert min(by_topic.values()) >= 3
    ids = {topic["id"] for topic in help_chat.HELP_TOPICS}
    assert set(by_topic) <= ids


@pytest.mark.parametrize(("question", "expected"), BANK)
def test_a_paraphrase_reaches_its_topic_first(question, expected):
    got = [topic["id"] for topic in help_chat.topics_for(question)]
    assert got[:1] == [expected], got
