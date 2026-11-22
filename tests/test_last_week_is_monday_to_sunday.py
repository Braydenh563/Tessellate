"""LEDGER L804, owner 2026-11-12: "last week" in a filter is the Monday to
Sunday before this one, never the seven days back from now."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import filters, slash

#: A Thursday, so seven days back (5 to 12 November) and last Monday to
#: Sunday (2 to 8 November) differ at both ends.
NOW = datetime(2026, 11, 12, 15, 0)


@pytest.mark.parametrize("said, kind", [("edited last week", "edited"), ("made last week", "created")])
def test_a_filter_reads_last_week_as_monday_to_sunday(said, kind):
    (found,) = filters.read(said, NOW)["filters"]
    assert (found["kind"], found["start"], found["end"]) == (kind, "2026-11-02", "2026-11-08")


def test_slash_made_last_week_reads_the_same_week():
    start, end, _phrase = slash._window("last week", NOW.date())
    assert (start.isoformat(), end.isoformat()) == ("2026-11-02", "2026-11-08")
