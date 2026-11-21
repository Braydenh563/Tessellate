"""Import cost of the composer's word tables (Brief 62, LEDGER L699).

The tables live as JSON in `tessellate/data` and are read at first use, so
importing `question_noise` must read none of its tables. `composer_tables.json`
feeds tables the module merges at import (`EXTRA_PHRASES`, the synonym groups), so
it is read then, once; only the question-noise tables are lazy. The structural checks
are exact; the timing check is a coarse ceiling, not a benchmark: each run is
a fresh interpreter, five runs, the median.

Measured 2026-11-21 on the dev box (warm bytecode, spelling and act_registry
already imported, five fresh interpreters, 9.2 to 9.6 ms): question_noise plus
composer_tables import in about 9.4 ms. The ceiling is 100 ms, about 10 times that, so a loaded CI core passes
while a return to building the 5,000-entry tables at import would not be
hidden: the structural checks catch an eager file read exactly.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path

from tessellate import data

ROOT = Path(__file__).resolve().parent.parent
BUDGET_MS = 100.0

_PROBE = """
import json, time
import tessellate.ai.spelling, tessellate.ai.act_registry  # shared, not ours to measure
start = time.perf_counter()
import tessellate.ai.question_noise, tessellate.ai.composer_tables
ms = (time.perf_counter() - start) * 1000
from tessellate import data
print(json.dumps({"ms": ms, "read": sorted(data.loaded())}))
"""


def _probe() -> dict:
    out = subprocess.run(
        [sys.executable, "-c", _PROBE], cwd=ROOT, capture_output=True, text=True, check=True,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    return json.loads(out.stdout)


def test_import_reads_no_question_noise_table() -> None:
    read = _probe()["read"]
    assert not [name for name in read if name.startswith("noise_")], read


def test_import_cost_is_under_the_budget() -> None:
    median = statistics.median(_probe()["ms"] for _ in range(5))
    assert median < BUDGET_MS, f"median import {median:.1f} ms, budget {BUDGET_MS} ms"


def test_tables_are_read_on_first_use_and_once() -> None:
    from tessellate.ai import question_noise

    assert "u" in question_noise.SLANG
    assert "noise_slang.json" in data.loaded()
    assert data.table("noise_slang.json") is data.table("noise_slang.json")


def test_every_data_file_is_packaged() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"tessellate.data" = ["*.json"]' in pyproject
    for spec in ("linux", "windows"):
        text = (ROOT / "packaging" / spec / "tessellate.spec").read_text(encoding="utf-8")
        assert '"tessellate" / "data"), "tessellate/data"' in text, spec
    assert sorted(p.name for p in data.DATA_DIR.glob("*.json"))
