"""CodeQL bisect probe: the D1 test in its new shape (identity, importlib)."""

from __future__ import annotations

import importlib


def test_pin_clock_reaches_a_module_that_imported_user_now_by_name(monkeypatch):
    from datetime import datetime

    from tessellate.core import config
    from tests._clock import pin_clock

    routes_chat = importlib.import_module("tessellate.api.routes_chat")
    when = datetime(2026, 8, 1, 9, 0)
    pin_clock(monkeypatch, when)
    assert config.user_now() == when
    assert routes_chat.user_now is config.user_now
