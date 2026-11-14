"""L595: the usage list's unused features feed the weekly offer (UI_MODERNISATION
statistics row 4): the dashboard's This week card offers one a week."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope

ROOT = Path(__file__).resolve().parent.parent
STATS = _js_scope.unwrapped((ROOT / "frontend" / "js" / "statistics.js").read_text(encoding="utf-8"))


def _fn(name: str) -> str:
    start = STATS.index(f"function {name}(")
    return STATS[start : STATS.index("\n}\n", start) + 2]


def _offer(unused, as_of):
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = f"{_fn('statsWeeklyOffer')}\nprocess.stdout.write(JSON.stringify(statsWeeklyOffer({json.dumps(unused)}, {json.dumps(as_of)}) ?? null));"
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_one_feature_a_week_the_same_all_week_and_another_the_next():
    unused = ["tab:graph", "Open the whiteboard", "Translate this", "Record a meeting"]
    week = {_offer(unused, day) for day in ("2026-11-09", "2026-11-11", "2026-11-15")}
    assert len(week) == 1 and week <= set(unused)
    assert _offer(unused, "2026-11-16") != _offer(unused, "2026-11-15")


def test_the_server_s_as_of_is_a_datetime_and_reads_as_its_day():
    unused = ["a", "b", "c"]
    assert _offer(unused, "2026-11-14T10:20:30.123456") == _offer(unused, "2026-11-14")
    assert _offer(unused, "not a date") is None


def test_nothing_is_offered_when_everything_is_used():
    assert _offer([], "2026-11-14") is None
    assert _offer(None, "2026-11-14") is None


def test_the_week_card_offers_it_and_opens_it():
    start = STATS.index("async function renderWeekWidget(")
    body = STATS[start : STATS.index("\n}\n", start)]
    assert "statsWeeklyOffer(" in body and "statsUnused(" in body
    assert "statsOpenFeature(" in body
