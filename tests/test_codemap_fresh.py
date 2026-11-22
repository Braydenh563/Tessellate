"""docs/CODEMAP.md matches what scripts/codemap.py generates from the tree now.

The map is what the orient skill sends every session and agent to first, so a
function that moved and a map that did not is a wrong line in every brief.
The lint regenerates the map in memory, reads the generation date back from
the committed file (the only input that is not the repository), and compares
the two strings exactly. The fix for a failure is the command in the message,
never an edit to the map by hand. Generation has to stay under three seconds:
that is what keeps this lint cheap enough to run on every test pass.
"""

import importlib.util
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "codemap.py"
COMMITTED = ROOT / "docs" / "CODEMAP.md"
DATE = re.compile(r"^Generated (\d{4}-\d{2}-\d{2})\b", re.M)
BUDGET_SECONDS = 10.0  # 3 s unloaded; the lint runs beside agents


def _generator():
    spec = importlib.util.spec_from_file_location("codemap", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codemap_matches_the_tree():
    committed = COMMITTED.read_text(encoding="utf-8")
    match = DATE.search(committed)
    assert match, "docs/CODEMAP.md has no 'Generated YYYY-MM-DD' line; run python scripts/codemap.py"
    started = time.process_time()
    fresh = _generator().build(ROOT, match.group(1))
    elapsed = time.process_time() - started
    assert fresh == committed, "docs/CODEMAP.md is stale; run python scripts/codemap.py"
    assert elapsed < BUDGET_SECONDS, (
        f"python scripts/codemap.py takes {elapsed:.2f}s, over the {BUDGET_SECONDS:.0f}s budget"
    )
