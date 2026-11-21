"""One fixed clock for a test (CLAUDE.md section 8: tests use a fixed clock, never the real one).

`user_now` is imported by name into many modules (`from tessellate.core.config import
user_now`), so patching one module left the others on the real clock: on 2026-11-21 a
note dated "21 November" read as today's and "the 16th" was in the past. `pin_clock`
patches the root and every loaded module holding it, so one call covers the app.
`tests/test_fixed_clock_lint.py` keeps tests on it."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime

from tessellate.core import config

_REAL = config.user_now


def pin_clock(monkeypatch, now: datetime | Callable[[], datetime]) -> None:  # noqa: ANN001
    """`user_now` answers `now` (or `now()`, for a clock a test moves) everywhere."""
    def fixed(_config=None):  # noqa: ANN001, ANN202
        return now() if callable(now) else now

    monkeypatch.setattr(config, "user_now", fixed)
    for name, module in list(sys.modules.items()):
        if name.startswith("tessellate") and getattr(module, "user_now", None) is _REAL:
            monkeypatch.setattr(module, "user_now", fixed)
