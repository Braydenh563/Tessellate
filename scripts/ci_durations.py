"""Sum a pytest junit file by test file, so one CI run shows where the suite's time goes (OPEN W24 D4).

`pytest --durations=15` names only the fifteen slowest tests; the tail (thousands of one-second tests) is
invisible there. This prints the files by total seconds and the share of the whole, to the job summary.

    python scripts/ci_durations.py junit.xml [top]
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


def by_file(path: str) -> tuple[dict[str, float], dict[str, int]]:
    secs: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)
    for case in ET.parse(path).getroot().iter("testcase"):
        name = (case.get("classname") or "").split(".")
        # classname is dotted: tests.test_x or tests.test_x.TestClass; the file is the second part
        key = "/".join(name[:2]) + ".py" if len(name) > 1 else (case.get("file") or "?")
        secs[key] += float(case.get("time") or 0.0)
        count[key] += 1
    return secs, count


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else "junit.xml"
    top = int(argv[2]) if len(argv) > 2 else 40
    secs, count = by_file(path)
    total = sum(secs.values()) or 1.0
    print(f"### Test time by file (sum of {sum(count.values())} tests, {total:,.0f} s of test CPU)\n")
    print("| file | tests | seconds | share |\n| --- | ---: | ---: | ---: |")
    for key, s in sorted(secs.items(), key=lambda kv: -kv[1])[:top]:
        print(f"| {key} | {count[key]} | {s:,.0f} | {100 * s / total:.1f}% |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
