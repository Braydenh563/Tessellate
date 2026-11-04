"""A quoted sentence is plain reading text (INBOX 1602).

The owner: "I dont like the way the composer quotes stuff". A sentence said
from a note, inside a list item, drew a left bar on every line it wrapped onto
and was greyed; a list item wrapped onto an indented line was read as an item
and a stray sentence ("Hub-finish-ui and." then "O47-merge-wip are in main").
Class: every shape of quote (quoted, shifted) draws no bar and keeps ink, and
every shape of wrapped item is one unit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.ai import composer_read

ROOT = Path(__file__).resolve().parents[1]
SHEET = (ROOT / "frontend/css/ask-compose-lazy.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    found = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", SHEET)
    assert found, selector
    return found.group(1)


@pytest.mark.parametrize("selector", [".said", ".said-shifted"])
def test_a_said_sentence_draws_no_bar_and_keeps_full_ink(selector):
    body = _rule(selector)
    for prop in ("box-shadow", "border", "border-left", "border-inline-start", "padding-inline-start", "background", "box-decoration-break"):
        assert not re.search(rf"(?m)^\s*{prop}\s*:", body), (selector, prop)
    assert "--muted" not in body and "opacity" not in body


def test_the_quoted_sentence_is_in_ink():
    assert "color: var(--ink)" in _rule(".said")


def _units(content: str) -> list[tuple[str, str]]:
    view = composer_read.read_note({"id": 1, "content": content}, 0)
    return [(s.kind, s.text) for s in view.sentences]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        #: A bullet wrapped onto an indented line.
        ("Status\n\n- hub-finish-ui and\n  O47-merge-wip are in main\n- next one is here", ["Hub-finish-ui and O47-merge-wip are in main", "Next one is here"]),
        #: Four spaces, and a tab.
        ("Status\n\n- hub-finish-ui and\n    O47-merge-wip are in main\n- next one is here", ["Hub-finish-ui and O47-merge-wip are in main", "Next one is here"]),
        ("Status\n\n- hub-finish-ui and\n\tO47-merge-wip are in main\n- next one is here", ["Hub-finish-ui and O47-merge-wip are in main", "Next one is here"]),
        #: A numbered item, and a task.
        ("Status\n\n1. hub-finish-ui and\n   O47-merge-wip are in main\n2. next one is here", ["Hub-finish-ui and O47-merge-wip are in main", "Next one is here"]),
        ("Status\n\n- [ ] hub-finish-ui and\n  O47-merge-wip are in main\n- [x] next one is here", ["Hub-finish-ui and O47-merge-wip are in main", "Next one is here"]),
        #: Wrapped twice, and with an abbreviation at the wrap.
        ("Status\n\n- hub-finish-ui and\n  O47-merge-wip are\n  in main now\n- next one is here", ["Hub-finish-ui and O47-merge-wip are in main now", "Next one is here"]),
        ("Status\n\n- ask Dr.\n  Smith about the plan\n- next one is here", ["Ask Dr. Smith about the plan", "Next one is here"]),
    ],
)
def test_a_wrapped_list_item_is_one_unit(content, expected):
    units = _units(content)
    assert [t for k, t in units] == expected
    assert all(k in ("item", "task") for k, t in units)


def test_a_line_after_a_blank_line_is_not_swallowed_by_the_item():
    units = _units("Status\n\n- hub-finish-ui is in main\n\n  Then the gaming mouse was shipped on Friday")
    assert units[0] == ("item", "Hub-finish-ui is in main")
    assert len(units) == 2


def test_an_unindented_line_after_an_item_stays_its_own_sentence():
    units = _units("Status\n\n- hub-finish-ui is in main\nThe gaming mouse was shipped on Friday")
    assert units[0] == ("item", "Hub-finish-ui is in main")
    assert units[1][1] == "The gaming mouse was shipped on Friday"
