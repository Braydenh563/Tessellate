"""Audit 1028 E17: notes written today were "the newest a day ago", the age rounded up to one."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from tessellate.ai import composer_digest as digest

TODAY = date(2026, 11, 2)


def _views(*days_back: int):
    return [SimpleNamespace(written=date.fromordinal(TODAY.toordinal() - d), note={"tags": []}) for d in days_back]


@pytest.mark.parametrize("seed", [0, 1])
@pytest.mark.parametrize("days_back", [(0, 0), (0, 3), (0, 15), (0, 8, 16)])
def test_a_note_written_today_is_today_never_a_day_ago(seed, days_back):
    token = digest._SEED.set(seed)
    try:
        said = digest._pattern(_views(*days_back), TODAY)
    finally:
        digest._SEED.reset(token)
    assert said and "today" in said and "a day ago" not in said and "a day old" not in said, said


def test_a_note_from_yesterday_is_still_a_day_ago():
    assert "a day ago" in digest._pattern(_views(1, 2), TODAY)
