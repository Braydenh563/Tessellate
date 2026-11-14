"""L-chat-64, `rapidfuzz`'s first use: the names a "no tag called X" line offers as close (`object_acts._close`) are
read by WRatio, so a slip, part of a name and the same words in another order all find it; difflib's ratio found
only the first."""

from __future__ import annotations

import pytest

from tessellate.ai import object_acts

NAMES = ["gym", "launch", "back to school", "budget", "garden", "meals", "reading list", "work"]


@pytest.mark.parametrize(
    ("typed", "found"),
    [("launh", "launch"), ("gmy", "gym"), ("budgt", "budget"), ("school back", "back to school"), ("list reading", "reading list"), ("reading", "reading list")],
)
def test_a_name_near_the_typed_one_is_offered(typed, found):
    assert found in object_acts._close(typed, NAMES)  # noqa: SLF001


@pytest.mark.parametrize("typed", ["zebra", "xylophone", "cat"])
def test_a_word_near_nothing_offers_nothing(typed):
    assert object_acts._close(typed, NAMES) == []  # noqa: SLF001


def test_at_most_three_and_the_nearest_first():
    near = object_acts._close("gardn", [*NAMES, "gardens", "garden party", "garden shed"])  # noqa: SLF001
    assert len(near) <= 3 and near[0] == "garden"
