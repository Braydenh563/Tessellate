"""CI ran 90 minutes and was cancelled (2026-11-12): the autonomous loop ran
on `jobs.thread` without a stop, so `jobs.join_threads` (every app test's
teardown) waited its full 5 s for a thread that sleeps for hours."""

from __future__ import annotations

import time

from tessellate.ai import autonomous
from tessellate.core import jobs


def test_the_autonomous_loop_is_stoppable_and_teardown_does_not_wait_for_it():
    autonomous.start()
    try:
        assert any(row["name"] == "autonomous-agent" and row["stoppable"] for row in jobs.threads())
        began = time.monotonic()
        jobs.join_threads(timeout=3.0)
        assert time.monotonic() - began < 1.0
    finally:
        autonomous.stop()
