"""Ticking a goal's item keeps focus on that item's checkbox after the list is rebuilt (Brief 98).

The view re-reads `/goals` after every change and replaces its cards, so without
the restore the focus fell to the page. A real Chromium runs goals-view.js over
stubbed helpers; skipped where Playwright is not installed."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAYWRIGHT = Path("/opt/node22/lib/node_modules/playwright")


@pytest.mark.skipif(not (shutil.which("node") and PLAYWRIGHT.is_dir()), reason="needs node and Playwright")
def test_a_tick_and_an_added_line_keep_their_focus():
    run = subprocess.run(
        ["node", str(ROOT / "tests" / "goals_focus_probe.js"), str(ROOT / "frontend" / "js" / "goals-view.js")],
        capture_output=True, text=True, timeout=90, check=False,
    )
    assert run.returncode == 0, run.stderr
    seen = json.loads(run.stdout.strip().splitlines()[-1])
    assert seen["tick"] == {"checked": True, "active": "2", "tag": "INPUT", "progress": 50}
    assert seen["add"] == {"active": "add-line", "items": 3}
