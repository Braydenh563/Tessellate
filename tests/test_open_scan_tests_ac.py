"""The tests in tests/test_[a-c]* read as open only where a LEDGER row says so
(L-graph-19, 2026-11-14: 211 open_scan hits swept to 2). A hit left here must
be a strict xfail whose reason names an open LEDGER row; anything else is a
comment to reword, a name to change, or work to log first."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import open_scan  # noqa: E402

LEDGER = (ROOT / "docs" / "roadmap" / "LEDGER.md").read_text(encoding="utf-8")
OPEN_ROWS = set(re.findall(r"^- \[ \] \*\*(L-[\w-]+)\*\*", LEDGER, re.M))


def test_every_hit_in_tests_a_to_c_is_a_strict_xfail_naming_an_open_row():
    owned = {p for paths in open_scan.OWNERS.values() for p in paths}
    paths = [f for f in open_scan.files() if re.match(r"^tests/test_[a-c]", f) and f not in owned]
    assert len(paths) > 200, len(paths)
    loose = []
    for path, line, text in open_scan.hits(paths):
        row = re.search(r"xfail\(strict=True, reason=\".*LEDGER (L-[\w-]+)\)", text)
        if not row or row.group(1) not in OPEN_ROWS:
            loose.append(f"{path}:{line}: {text.strip()[:100]}")
    assert loose == [], loose
