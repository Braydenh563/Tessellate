"""Complexity and import cycles, ratcheted (WORLD_CLASS_PLAN 26.2, decision 63).

`scripts/complexity.py` walks `src/tessellate` for cyclomatic complexity and
import cycles. The seed `complexity_seed.json` holds every function over 15
on 2026-10-10 with the number it had (260 functions; the worst is
`_note_facts` and `_stream_lines` at 105). A function over 15 that is not in
the seed fails; a seeded function that grew fails; one that fell to 15 or
below, or went away, fails until its row is deleted, so the seed only
shrinks. Refresh a number downward with
`python scripts/complexity.py` and edit the JSON by hand.

Cycles: at load there are none and it stays none. Counting imports inside
functions there is one group of 20 modules (the AI package's lazy imports);
it may not grow.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((Path(__file__).parent / "complexity_seed.json").read_text(encoding="utf-8"))
LAZY_CYCLE_MODULES = 20

_spec = importlib.util.spec_from_file_location("complexity", ROOT / "scripts" / "complexity.py")
complexity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(complexity)


def test_no_new_function_over_15_and_none_grows() -> None:
    now = {k: v[0] for k, v in complexity.functions().items()}
    new = sorted(k for k in now if k not in SEED)
    grew = sorted(f"{k}: {SEED[k]} to {now[k]}" for k in now if k in SEED and now[k] > SEED[k])
    assert not new, "a function over 15; split it by the state or the step:\n  " + "\n  ".join(new)
    assert not grew, "more complex than its seed:\n  " + "\n  ".join(grew)


def test_the_seed_only_shrinks() -> None:
    now = {k: v[0] for k, v in complexity.functions().items()}
    stale = sorted(f"{k}: {SEED[k]} now {now.get(k, 'gone or 15 or less')}" for k in SEED if now.get(k, 0) < SEED[k])
    assert not stale, "less complex than its seed; lower or delete the row in complexity_seed.json:\n  " + "\n  ".join(stale)


def test_no_import_cycle_at_load() -> None:
    assert complexity.cycles() == []


def test_the_lazy_import_cycle_does_not_grow() -> None:
    groups = complexity.cycles(lazy=True)
    assert len(groups) <= 1 and all(len(g) <= LAZY_CYCLE_MODULES for g in groups), [len(g) for g in groups]


def test_the_performance_rules_have_a_zero_baseline() -> None:
    """Q20: none of the PERF rules are open, so the baseline is zero and a new one fails this test (where ruff is
    installed). Making complexity.yml fail on them too is a CI definition edit, left for the owner (HANDOVER)."""
    import shutil
    import subprocess

    ruff = shutil.which("ruff") or str(ROOT / ".venv" / "bin" / "ruff")
    if not Path(ruff).exists():
        return
    done = subprocess.run([ruff, "check", "src", "--select", "PERF", "--output-format=concise"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout
