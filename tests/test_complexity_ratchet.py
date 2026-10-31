"""The CI "Complexity and perf scan" count, ratcheted so it can only go down.

`.github/workflows/complexity.yml` runs ruff's C901 (McCabe over 15) and PERF
rules over `src`. This runs the same command and fails when the count is
above `MAX_FINDINGS`, the number the last cleanup ended at. Fixing a finding
and lowering the number in the same commit is the only way the number
moves; raising it is never the answer, split the function or write the
comprehension instead. (`test_complexity.py` is the sibling ratchet over the
per-function seed and the import cycles.)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAX_FINDINGS = 20


def _ruff() -> list[str] | None:
    found = shutil.which("ruff")
    if found:
        return [found]
    probe = subprocess.run([sys.executable, "-m", "ruff", "--version"], capture_output=True, check=False)
    return [sys.executable, "-m", "ruff"] if probe.returncode == 0 else None


def test_the_complexity_and_perf_scan_count_only_goes_down() -> None:
    ruff = _ruff()
    if ruff is None:
        pytest.skip("ruff is not installed")
    done = subprocess.run(
        [
            *ruff, "check", "src", "--select", "C901,PERF",
            "--config", "lint.mccabe.max-complexity = 15",
            "--output-format=concise", "--exit-zero", "--no-cache",
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    found = re.search(r"Found (\d+) errors?", done.stdout)
    count = int(found.group(1)) if found else 0
    assert count <= MAX_FINDINGS, (
        f"{count} complexity or perf findings, over the {MAX_FINDINGS} this ratchet allows:\n"
        + "\n".join(line for line in done.stdout.splitlines() if " C901 " in line or " PERF" in line)
    )
