"""Gaps in the composer's acts found by the ledger sweep (L47 and kin): each
sentence read, planned and, where it writes, run on a real notebook.
Fixed clock: Thursday 12 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt

from tessellate.ai import acts
from tessellate.entry import manager

NOW = dt.datetime(2026, 11, 12, 10, 0)


def test_rename_with_a_to_in_both_names_picks_the_note_that_exists(session):
    manager.create_entry(session, "# Trip to Spain\n\nFlights booked.")
    manager.create_entry(session, "# Trip\n\nOther.")
    session.commit()
    parsed = acts.parse("rename Trip to Spain to Trip to Portugal", NOW)
    card = acts.preview(session, parsed)["card"]
    assert "Trip to Portugal" in card["label"]
    assert "Trip to Spain" in card["label"]
