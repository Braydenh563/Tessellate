"""CodeQL bisect probe: the D1 test in its new shape (identity, importlib)."""

from __future__ import annotations



def test_pin_clock_reaches_a_module_that_imported_user_now_by_name(monkeypatch):
    """A loaded module that holds `user_now` and `utcnow` by name reads the pinned
    clock. A stub module stands in for the app's: reaching a route module at run
    time (routes_chat) cost CodeQL's Analyze its 20 minutes (bisect, #248). The
    `_clock_holders` lint above keeps every real by-name importer in HOLDERS."""
    import sys
    import types
    from datetime import datetime, timezone

    from tessellate.core import config, database
    from tests import _clock

    stub = types.ModuleType("tests._clock_stub_holder")
    stub.user_now = config.user_now
    stub.utcnow = database.utcnow
    monkeypatch.setitem(sys.modules, stub.__name__, stub)
    monkeypatch.setattr(
        _clock, "HOLDERS", (*_clock.HOLDERS, (stub.__name__, "user_now"), (stub.__name__, "utcnow"))
    )
    when = datetime(2026, 8, 1, 9, 0)
    _clock.pin_clock(monkeypatch, when)
    assert stub.user_now() == when
    assert stub.utcnow() == when.astimezone(timezone.utc)
