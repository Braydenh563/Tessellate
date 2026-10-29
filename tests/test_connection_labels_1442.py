"""INBOX 1442: a note's name on the Connections column, its forgotten notes
and link chips is plain words; "**Gym Routine Overview**" showed its stars."""

from __future__ import annotations

import pytest

from tessellate.api import routes_entries
from tessellate.entry import manager

CASES = [
    ("**Gym Routine Overview** Frequency: 4 days", "Gym Routine Overview Frequency: 4 days"),
    ("# *Lisbon* trip", "Lisbon trip"),
    ("`code` and ~~strike~~ words", "code and strike words"),
    ("[[Budget]] for __May__", "Budget for May"),
]


@pytest.mark.parametrize("content,label", CASES)
def test_a_connection_label_is_plain_words(content, label):
    class E:
        pass

    entry = E()
    entry.content, entry.is_private = content, False
    assert manager.plain_label(content) == label
    assert "*" not in routes_entries._preview(content, 80) and "`" not in routes_entries._preview(content, 80)


def test_the_column_and_the_forgotten_list_use_the_one_label():
    import inspect

    from tessellate.api import routes_resurface

    assert "plain_label" in inspect.getsource(routes_entries._connection_label)
    assert "plain_label" in inspect.getsource(routes_resurface)
