"""Wait for the job pool to drain, for tests whose route queues the work."""

from __future__ import annotations

import time

from tessellate.core import jobs


def pool_idle(seconds: float = 10.0) -> bool:
    """True once nothing is queued or running on the app's pool."""
    ends = time.monotonic() + seconds
    pool = jobs.pool()
    while time.monotonic() < ends:
        if pool.queued_count() == 0 and pool.running_count() == 0:
            return True
        time.sleep(0.01)
    return False
