"""Count and check the tests that read source text instead of running behaviour.

    python scripts/source_text_tests.py            # prints the count
    python scripts/source_text_tests.py --baseline # rewrite tests/source_text_baseline.txt

A test that greps `frontend/` or `src/` for a string proves a string exists,
not that the app works. Some must (a lint over CSS, a CSP, a load order), so
the rule is not "never" but "say why": a source-text test file added after the
baseline carries a module docstring that begins "Source text:" and gives the
reason behaviour cannot be asserted. `tests/test_source_text_docstrings.py`
enforces it; `scripts/gate.sh` prints the count (L-general-9).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
BASELINE = TESTS / "source_text_baseline.txt"
READS = re.compile(r"\.read_text\(|app_js_text\(|\.read_bytes\(")
SOURCE = re.compile(r"frontend|\"src\"|'src'|src/tessellate|app_js_text|\.github|packaging|docker|docs")


def source_text_files() -> list[str]:
    found = []
    for path in sorted(TESTS.glob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if READS.search(text) and SOURCE.search(text):
            found.append(path.name)
    return found


if __name__ == "__main__":
    names = source_text_files()
    if "--baseline" in sys.argv:
        BASELINE.write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"{len(names)} of {len(list(TESTS.glob('test_*.py')))} test files read source text")
