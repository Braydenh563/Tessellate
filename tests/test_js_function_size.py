"""A JS function-size ratchet, the twin of the Python complexity seed (L-whiteboard-78).

ruff's C901 covers `src` only, so the app's scripts had no limit at all: the
board's `initWhiteboard` reached 4,000+ lines. `js_size_seed.json` holds every
function body over `CAP` lines (tests/_js_sizes.py) as measured 2026-11-22. A
new function over the cap fails, a seeded one that grew fails, and a row whose
function fell under the cap or went away fails until it is deleted, so the
seed only shrinks. Raising a number is never the fix: split the function by job.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests._js_sizes import CAP, sizes

SEED = json.loads((Path(__file__).parent / "js_size_seed.json").read_text(encoding="utf-8"))
NOW = sizes()


def test_no_new_function_over_the_cap() -> None:
    new = sorted(f"{k}: {n} lines" for k, n in NOW.items() if k not in SEED)
    assert not new, f"over {CAP} lines and not seeded; split it by job:\n  " + "\n  ".join(new)


def test_no_seeded_function_grew() -> None:
    grew = sorted(f"{k}: {NOW[k]} lines, seeded {n}" for k, n in SEED.items() if NOW.get(k, 0) > n)
    assert not grew, "longer than its seed; split it rather than raise the row:\n  " + "\n  ".join(
        grew
    )


def test_the_seed_only_shrinks() -> None:
    stale = sorted(k for k in SEED if k not in NOW)
    assert not stale, (
        f"now under {CAP} lines or gone; delete the row in js_size_seed.json:\n  "
        + "\n  ".join(stale)
    )
