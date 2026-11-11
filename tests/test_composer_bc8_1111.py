"""Batch BC8 (fable composer audits 1110, rechecked 2026-11-11).
F3: a bare "remove milk" names a thing on a list, not a note, so it never
proposes binning the note that happens to hold the word; naming the note
("delete the Shopping note") still does."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands
from tessellate.entry import manager

NOW = datetime(2026, 11, 10, 9, 0)


def _plan(session, text: str) -> dict:
    parsed = commands.read_typed(text, NOW)
    assert parsed is not None and parsed["intent"] == "delete", (text, parsed)
    return commands.plan(session, parsed)


@pytest.mark.parametrize("text", ["remove milk", "delete butter", "remove the milk"])
def test_f3_a_bare_word_held_only_in_a_notes_body_never_bins_that_note(session, text):
    manager.create_entry(session, "# Shopping\n\n- [ ] milk\n- [ ] butter\n- [x] bread")
    planned = _plan(session, text)
    assert "card" not in planned, planned
    assert "delete the" in planned["line"].lower() and "shopping" in planned["line"].lower(), planned["line"]


def test_f3_a_titled_note_named_bare_is_still_binned(session):
    manager.create_entry(session, "# Gym log\n\nSquats on Monday.")
    planned = _plan(session, "delete gym log")
    assert planned.get("card") and "Gym log" in planned["line"], planned


def test_f3_naming_the_note_still_bins_it(session):
    manager.create_entry(session, "# Shopping\n\n- [ ] milk")
    planned = _plan(session, "delete the shopping note")
    assert planned.get("card") and "Shopping" in planned["line"], planned
