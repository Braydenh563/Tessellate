"""LEDGER L624: the 800-line bar. A file over it has a cap in file_size_caps.json
(its length on 2026-11-12 plus a tenth, room for other sessions' work); the cap
only falls, and a new file stays under the bar.
Splits land one file at a time; this keeps the total from growing back."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAR = 800
CAPS = json.loads((ROOT / "tests" / "file_size_caps.json").read_text(encoding="utf-8"))


def _lengths() -> dict[str, int]:
    names = subprocess.run(
        ["git", "ls-files", "src/*.py", "frontend/js/*.js"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    return {n: len((ROOT / n).read_text(encoding="utf-8").splitlines()) for n in names if (ROOT / n).exists()}


def test_no_file_grows_past_its_cap_and_no_new_file_passes_the_bar():
    over = [
        f"{name} {length} > {CAPS.get(name, BAR)}"
        for name, length in _lengths().items()
        if length > CAPS.get(name, BAR)
    ]
    assert not over, over


def test_the_caps_are_lowered_as_files_shrink():
    lengths = _lengths()
    slack = [f"{n} cap {c}, now {lengths.get(n, 0)}" for n, c in CAPS.items() if lengths.get(n, 0) < c * 0.75]
    assert not slack, "lower these caps in tests/file_size_caps.json: " + "; ".join(slack)
