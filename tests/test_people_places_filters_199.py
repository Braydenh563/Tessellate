"""L-chat-199: a person or a place said as a filter ("notes with Sam in them",
"where Hannah is mentioned", "notes from Perth") reads as the `mention` filter
the chips show; a month or a capitalised word that is not a name does not."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import filters

NOW = datetime(2026, 11, 9, 9)


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("notes with Sam in them", "Sam"),
        ("notes where Hannah is mentioned", "Hannah"),
        ("notes from Perth", "Perth"),
        ("notes I wrote in Lisbon", "Lisbon"),
        ("notes about Sam", None),
    ],
)
def test_a_person_or_place_is_a_mention_filter(text, name):
    got = filters.read(text, NOW)["filters"]
    if name is None:
        assert not got
    else:
        assert [(f["kind"], f["name"]) for f in got] == [("mention", name)]


@pytest.mark.parametrize("text", ["notes from June", "notes in March", "notes from last week", "notes in the garden"])
def test_a_date_or_a_common_word_is_not_a_place(text):
    assert not [f for f in filters.read(text, NOW)["filters"] if f["kind"] == "mention"]
