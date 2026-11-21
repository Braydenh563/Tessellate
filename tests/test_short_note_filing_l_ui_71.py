"""L-ui-modernisation-71 (IDEAS.md): "I wrote 'ai is cool' as a note and it was filed
under sketches". With no model, a short note goes where its one topic word
points, and nowhere when no category matches; it never lands in Sketches."""

from __future__ import annotations

import pytest

from tessellate.ai import lexical_filing
from tessellate.entry import manager

SKETCHES = ["quick sketch of the garden layout", "drew a cat in pencil", "sketch: bridge over the river"]
WORK = ["meeting with Sam about the budget", "quarterly report due friday"]


def _seed(session, extra: dict[str, list[str]]) -> None:
    for name, notes in {"Sketches": SKETCHES, "Work": WORK, **extra}.items():
        for text in notes:
            manager.create_entry(session, text, category_name=name)
    session.commit()


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({"AI": ["trying a local llama model for summaries", "embeddings make search smarter"]}, "AI"),
        ({"Technology": ["trying a local llama model for summaries", "neural networks notes"]}, "Technology"),
        ({"Travel": ["train to Porto on monday", "book the hotel in Lisbon"]}, None),
    ],
)
def test_ai_is_cool_files_by_its_topic_or_not_at_all(session, extra, expected):
    _seed(session, extra)
    for text in ("ai is cool", "AI is cool", "i like ai"):
        decision = lexical_filing.decide(session, text)
        filed = decision.filed.name if decision.filed else None
        assert filed == expected, (text, filed)
