"""The day it is here, read in one place (audit 1031 AR8).

Eight call sites read `date.today()` for themselves, so a test that pinned
"today" for one of them left the rest on the real calendar. They all call
`today()` now; a test pins the day by patching this one name, and
`tests/test_drifted_copies_1031.py` fails a new `date.today()` anywhere else.
"""

from __future__ import annotations

from datetime import date


def today() -> date:
    """The local calendar date."""
    return date.today()
