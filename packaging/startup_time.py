"""Seconds from launch to the first 200 from /health (L-world-class-72).

    python packaging/startup_time.py --base http://127.0.0.1:8767 [--summary FILE] [--limit 120]

Run beside a just-started app. Prints one line, appends it to the CI job
summary file when given, and always exits 0 (no threshold yet: the numbers
first, a limit once there are enough runs). Exit 1 only if /health never
answers within `--limit`, since then there is no number to record.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from collections.abc import Callable


def seconds_to_health(
    base: str,
    limit: float = 120.0,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    fetch: Callable[[str], int] | None = None,
) -> float | None:
    """Seconds until `base`/health first answers 200, or None past `limit`."""

    def _status(url: str) -> int:
        try:
            with urllib.request.urlopen(url, timeout=2) as reply:  # noqa: S310
                return reply.status
        except OSError:  # URLError and timeouts: the app is not up yet
            return 0

    get = fetch or _status
    started = clock()
    while clock() - started <= limit:
        if get(base.rstrip("/") + "/health") == 200:
            return clock() - started
        sleep(0.1)
    return None


def summary_line(seconds: float | None) -> str:
    if seconds is None:
        return "Frozen Windows startup: /health never answered 200"
    return f"Frozen Windows startup: {seconds:.1f} s to the first 200 from /health"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--summary", help="a file to append the line to (GITHUB_STEP_SUMMARY)")
    parser.add_argument("--limit", type=float, default=120.0)
    args = parser.parse_args(argv)
    line = summary_line(seconds_to_health(args.base, args.limit))
    print(line)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as out:
            out.write(line + "\n")
    return 0 if "never" not in line else 1


if __name__ == "__main__":
    sys.exit(main())
