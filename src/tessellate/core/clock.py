"""The day it is here, read in one place (audit 1031 AR8).

Eight call sites read `date.today()` for themselves, so a test that pinned
"today" for one of them left the rest on the real calendar. They all call
`today()` now; a test pins the day by patching this one name, and
`tests/test_drifted_copies_1031.py` fails a new `date.today()` anywhere else.
`utc()` and `wall()` are the same for the time of day: no module reads
`datetime.now()` for itself (`tests/test_fixed_clock_lint.py`).
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone


def today() -> date:
    """The local calendar date."""
    return date.today()


def _now() -> datetime:
    """The person's clock: `config.user_now`, looked up by name each call so a
    test's pinned clock answers here too. Through `sys.modules`, not an
    import: `clock` imports nothing of the app, so the many modules below
    `config` that read the time through it close no import cycle
    (`tests/test_import_module_cycles.py`). Before `config` has loaded (a
    worker process that never imports it) the zone is this machine's, so the
    instant is enough."""
    config = sys.modules.get("tessellate.core.config")
    return config.user_now(None) if config is not None else datetime.now(timezone.utc)


def utc() -> datetime:
    """Now, timezone-aware UTC. A naive pinned clock is wall time on this
    machine, as `database.utcnow` reads it under `tests/_clock.pin_clock`."""
    return _now().astimezone(timezone.utc)


def wall() -> datetime:
    """This machine's wall time, naive, as `datetime.now()` gave it."""
    now = _now()
    return now if now.tzinfo is None else now.astimezone().replace(tzinfo=None)
