"""The tab's surfaces stay known until the tab really changes size (INBOX 1696 l).

The owner, 2026-11-08: "throwing the in-app companion actually froze my app",
with "companion-throw.js spotNow 7500ms (forced layout 6905ms)". Measured
(scratchpad/ui-sweeps/spotreads1696.js, Atlas on the Dashboard, 600 notes):
every throw's landing walked the page again, 149 to 299 box reads after the
release's writes, so the first of them paid for a whole page layout. The walk
is kept (`nameMarkBuddyIndex`) and dropped by a ResizeObserver on the tab, but a
ResizeObserver reports once as soon as it starts observing, so the walk was
dropped at the next frame every time and the landing never found it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


@needs_node
def test_the_observers_first_report_keeps_the_walk_and_a_real_resize_drops_it():
    js = "\n".join([
        "const nmb = { covers: 1 };",
        "let nameMarkBuddyIndex = null; let nameMarkBuddyIndexSize = null;",
        _fn("nameMarkBuddyIndexReset"),
        _fn("nameMarkBuddyIndexResized"),
        "const out = [];",
        "const e = (w, h) => [{ contentRect: { width: w, height: h } }];",
        "nameMarkBuddyIndex = { tab: 'dashboard', edges: [1] }; nameMarkBuddyIndexSize = null;",
        # The report a ResizeObserver makes as it starts observing.
        "nameMarkBuddyIndexResized(e(1200, 800)); out.push(!!nameMarkBuddyIndex);",
        # The same size again (a relayout that moved nothing).
        "nameMarkBuddyIndexResized(e(1200, 800)); out.push(!!nameMarkBuddyIndex);",
        # The tab really changed size.
        "nameMarkBuddyIndexResized(e(1000, 800)); out.push(!!nameMarkBuddyIndex);",
        "console.log(JSON.stringify(out));",
    ])
    res = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout) == [True, True, False]


def test_the_walk_is_observed_through_the_size_check_not_dropped_on_every_report():
    edges = _fn("nameMarkBuddyEdges")
    assert "new ResizeObserver(nameMarkBuddyIndexResized)" in edges
    assert "new ResizeObserver(nameMarkBuddyIndexReset)" not in edges
    # Each new observation starts from an unknown size: its first report is the one to keep.
    assert "nameMarkBuddyIndexSize = null" in edges
