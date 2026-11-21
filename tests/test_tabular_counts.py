"""Counts and totals use tabular figures (WORLD_CLASS_PLAN 7, "Numbers: tabular figures").

Forty class names ending in -count or -total drew their digits proportionally,
so a live tally shifted its neighbours. One zero-specificity rule in
07-whiteboard-misc.css covers the whole family; this holds that it stays.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_the_count_and_total_family_has_one_tabular_rule():
    rule = re.search(r":where\(([^)]*-count[^)]*)\)\s*\{([^}]*)\}", CSS)
    assert rule, "the :where rule for -count and -total classes is gone"
    assert "tabular-nums" in rule.group(2)
    for suffix in ("-count", "-total"):
        assert f'[class$="{suffix}"]' in rule.group(1) and f'[class*="{suffix} "]' in rule.group(1)
