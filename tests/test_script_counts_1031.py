"""The documents' script counts come from the code (audit 1031 AR10).

ARCHITECTURE.md and CLAUDE.md said "27 classic scripts" for a stretch of
index.html that now holds 28, and the page loads 36 scripts at boot out of 208
files. `scripts/codemap.py` computes the numbers (its Counts line carries them);
this holds every sentence that quotes one.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _counts() -> dict[str, int]:
    spec = importlib.util.spec_from_file_location("codemap_1031", ROOT / "scripts" / "codemap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.script_counts(ROOT)


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_the_map_carries_the_numbers():
    counts = _counts()
    line = next(row for row in _read("docs/CODEMAP.md").splitlines() if row.startswith("Counts:"))
    for label, value in counts.items():
        assert f"{label} {value}" in line, (label, value)


def test_every_sentence_that_counts_the_app_scripts_agrees():
    app = _counts()["app scripts"]
    found = []
    for name in ("CLAUDE.md", "docs/ARCHITECTURE.md", "docs/WORKING.md"):
        text = _read(name)
        for pattern, want in (
            (r"(\d+) classic scripts", app),
            (r"cut into the (\d+) files above", app),
            (r"tests read the (\d+)\s+as one text", app),
            (r"and the (\d+) files after it", app - 1),
        ):
            for match in re.finditer(pattern, text):
                found.append((name, match.group(0)))
                assert int(match.group(1)) == want, (name, match.group(0), want)
    assert len(found) >= 6, found  # the sentences exist, so a rewording cannot dodge the check


def test_the_documents_do_not_call_p5_on_demand_only():
    text = _read("docs/ARCHITECTURE.md")
    assert "loaded on demand by `ensureP5`" not in text
