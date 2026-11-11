"""Split the suite into parallel CI legs by test file (OPEN W24, CI time 1109).

`pytest --shard 2/3` keeps the files of the second of three legs and deselects the rest. The split is by file, so a
module-level cache (the overlay hours, the source-file cache) is built in one leg only, and it is a pure function of the
collected files and `WEIGHTS`, so every xdist worker of a leg picks the same tests. Files go to the leg with the least
estimated seconds so far, the heaviest first. Not named `test_*.py` on purpose, as `_app_js.py`."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

#: Seconds a test costs when its file is not in `WEIGHTS`: the suite is about 10,000 test-CPU seconds over 48,000 tests.
DEFAULT_PER_TEST = 0.2

#: Measured seconds of the files that are far from the default (CI 3.12 durations and local junit, 2026-11-11). A file
#: missing here costs `DEFAULT_PER_TEST` a test; add one when a CI "Test time by file" summary shows it off by a lot.
WEIGHTS: dict[str, float] = {
    "test_overlay_rest_1670.py": 330.0,
    "test_overlay_life_1670.py": 200.0,
    "test_overlay_hang_end_1683.py": 120.0,
    "test_overlay_ride_1670.py": 134.0,
    "test_overlay_modes_1107.py": 86.0,
    "test_overlay_moves.py": 65.0,
    "test_overlay_wander_1696.py": 65.0,
    "test_overlay_runner.py": 65.0,
    "test_overlay_doing_1718.py": 57.0,
    "test_overlay_travel_1683.py": 50.0,
    "test_overlay_roam_runner.py": 48.0,
    "test_overlay_roam.py": 43.0,
    "test_overlay_perch_small_1697.py": 43.0,
    "test_overlay_presence_1692.py": 40.0,
    "test_engine_dialogue.py": 40.0,
    "test_overlay_poof_1108.py": 36.0,
    "test_overlay_alive_1670.py": 35.0,
    "test_launcher_scripts.py": 20.0,
    "test_resurface_spec.py": 18.0,
    "test_search_engine_spec.py": 15.0,
    "test_backup_roundtrip_full.py": 13.0,
    "test_global_scope_ratchet.py": 12.0,
}

#: Files that stay together in the first leg: the ratchets that read the whole tree (and are checked serially on a
#: developer's machine) and the timing budgets, which a leg of unrelated heavy files would only make noisier.
def together(name: str) -> bool:
    return "ratchet" in name or name == "test_budgets.py"


def parse(spec: str) -> tuple[int, int]:
    """`"2/3"` -> (2, 3); anything else is an error, so a typo does not run the whole suite in every leg."""
    try:
        index, count = (int(part) for part in spec.split("/"))
    except ValueError:
        raise ValueError(f"--shard wants i/n, such as 1/2; got {spec!r}") from None
    if not 1 <= index <= count:
        raise ValueError(f"--shard {spec}: i must be from 1 to n")
    return index, count


def assign(counts: dict[str, int], count: int) -> dict[str, int]:
    """File name -> leg (0-based). `counts` is the tests per file."""
    weight = {name: WEIGHTS.get(name, DEFAULT_PER_TEST * n) for name, n in counts.items()}
    load = [0.0] * count
    leg: dict[str, int] = {}
    for name in sorted(n for n in counts if together(n)):
        leg[name] = 0
        load[0] += weight[name]
    for name in sorted((n for n in counts if n not in leg), key=lambda n: (-weight[n], n)):
        target = min(range(count), key=lambda i: (load[i], i))
        leg[name] = target
        load[target] += weight[name]
    return leg


def split(items: list, spec: str) -> tuple[list, list]:
    """(kept, dropped) of collected items for the leg `spec` names."""
    index, count = parse(spec)
    counts = Counter(Path(str(item.path)).name for item in items)
    leg = assign(dict(counts), count)
    kept, dropped = [], []
    for item in items:
        (kept if leg[Path(str(item.path)).name] == index - 1 else dropped).append(item)
    return kept, dropped
