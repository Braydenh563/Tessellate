"""Tests use a fixed clock, never the real one (CLAUDE.md section 8).

On 2026-11-21 five composer tests failed on py3.13: their fixture pinned
`user_now` on two or three modules, and the modules it missed (`from
tessellate.core.config import user_now` binds the name at import) read the real
day, so "21 November" was today and "the 16th" had passed. `tests/_clock.pin_clock`
pins every holder at once; these lints keep the suite on it."""


from __future__ import annotations


import ast


from pathlib import Path


def test_pin_clock_reaches_a_module_that_imported_user_now_by_name(monkeypatch):
    from datetime import datetime

    from tessellate.api import routes_chat
    from tessellate.core import config
    from tests._clock import pin_clock

    when = datetime(2026, 8, 1, 9, 0)
    pin_clock(monkeypatch, when)
    assert config.user_now() == when and routes_chat.user_now(None) == when


def test_a_row_made_under_a_pinned_clock_is_stamped_with_it(monkeypatch, session):
    """`created_at` defaults to `database.stamp`, which reads the pinned `utcnow`;
    before, a note made under a pinned 30 October was stamped with the real day."""
    from datetime import datetime, timezone

    from tessellate.core import clock
    from tessellate.entry import manager
    from tests._clock import pin_clock

    when = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    pin_clock(monkeypatch, when)
    entry = manager.create_entry(session, "# Pinned\n\nWritten on the pinned day.")
    session.commit()
    assert entry.created_at.replace(tzinfo=timezone.utc) == when
    assert clock.today() == when.date()


