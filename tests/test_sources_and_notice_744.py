"""L-chat-228 (INBOX 744 b and c): the answer to "test notes" names how many notes match and carries every one as a
source (the foot's cards), and the "only N of M sentences quoted" warning is the model draft's: a composed answer
that quotes 2 of 5 notes' sentences raises none, only one made mostly of picture readings does."""

from __future__ import annotations

from tessellate.ai import grounding
from tessellate.core.database import Entry
from tests.test_composer_route_688 import _ask

TITLES = ("test", "test board", "test draft", "test notes", "Soup")


def test_the_answer_carries_every_matching_note_as_a_source(client, session):
    for title in TITLES:
        session.add(Entry(content=f"# {title}\n\nThe {title} entry, written for the notebook."))
    session.commit()
    out = _ask(client, "test notes")
    carried = {e["content"].splitlines()[0] for e in out["meta"][-1]["raw_results"]}
    assert {f"# {t}" for t in TITLES[:4]} <= carried, carried
    assert "four notes" in out["text"].lower(), out["text"]
    assert "Soup" not in out["text"]


def test_a_composed_answer_quoting_two_of_five_sentences_raises_no_warning():
    rows = [{"sentence": "A.", "note_id": 1, "said": "quote"}, {"sentence": "B.", "note_id": 2, "said": "quote"}]
    support = grounding.composed_support(None, rows)
    assert support["by_model"] is False and support["low"] is False, support


def test_a_composed_answer_of_mostly_picture_readings_still_says_so():
    rows = [{"sentence": "A.", "note_id": 1, "said": "picture"}, {"sentence": "B.", "note_id": 2, "said": "picture"}, {"sentence": "C.", "note_id": 3, "said": "quote"}]
    assert grounding.composed_support(None, rows)["low"] is True
