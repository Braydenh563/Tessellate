"""Pin the user's clock in every module that holds it (one helper, not a list per test).

`user_now` is imported by name into a couple of dozen modules, and several
import it from `tessellate.core.config` at call time, so pinning three named
modules leaves the rest on the real day. On 2026-11-21 that turned four test
files red at once: a fixture dated "21 November" became today, "the 16th"
became December, and a week of notes from 10 November fell out of the window.
"""

from __future__ import annotations

import sys
from datetime import datetime


def pin_user_now(monkeypatch, now: datetime) -> None:
    for name, module in list(sys.modules.items()):
        if (name == "tessellate" or name.startswith("tessellate.")) and callable(getattr(module, "user_now", None)):
            monkeypatch.setattr(module, "user_now", lambda _config=None: now)
