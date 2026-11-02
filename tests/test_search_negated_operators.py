"""`-tag:`, `-kind:`, `-is:` and `-title:` rule hits out (shell audit 1028 S50 left them out).

A table of queries, so a new negated operator is one more row.
"""

from __future__ import annotations

import pytest

from tessellate.entry import manager
from tessellate.search import engine
from tessellate.search import query as query_understanding


@pytest.mark.parametrize(
    ("q", "key", "values"),
    [
        ("garden -tag:work", "tag", ["work"]),
        ("garden -tags:work,home", "tag", ["work", "home"]),
        ('garden -tag:"two words"', "tag", ["two words"]),
        ("garden -type:document", "kind", ["document"]),
        ("garden -is:favourite", "is", ["pinned"]),
        ("garden -title:plan", "title", ["plan"]),
    ],
)
def test_a_negated_operator_is_read_as_one(q, key, values):
    asked = query_understanding.understand(q)
    assert asked.without[key] == values
    assert asked.subject == "garden"
    #: Never taken as an unwanted word, never left behind as text.
    assert not asked.excluded and ":" not in asked.subject and not asked.filters[key]


def test_a_hyphenated_word_and_a_plain_exclusion_still_read_as_before():
    asked = query_understanding.understand("state-of-the-art garden -slugs")
    assert asked.excluded == ["slugs"] and not any(asked.without.values())


def test_a_negated_tag_drops_the_notes_that_carry_it(session):
    keep = manager.create_entry(session, "planting notes for the garden", tags=["garden"])
    drop = manager.create_entry(session, "planting notes for the work garden", tags=["work"])
    session.commit()
    ids = [hit.ref_id for hit in engine.search(session, "planting -tag:work", kinds=["note"], hybrid=False)]
    assert keep.id in ids and drop.id not in ids


def test_a_negated_flag_drops_the_pinned_note(session):
    pinned = manager.create_entry(session, "garden plan pinned")
    pinned.pinned = True
    plain = manager.create_entry(session, "garden plan plain")
    session.commit()
    ids = [hit.ref_id for hit in engine.search(session, "garden -is:pinned", kinds=["note"], hybrid=False)]
    assert plain.id in ids and pinned.id not in ids
