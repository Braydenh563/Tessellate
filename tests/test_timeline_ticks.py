"""The density strip's year and month labels, from D3's time scale (TIMELINE_PLAN
10 row 6, VC2).

`timeline-ticks.js` is a lazy file: it loads d3 (the graph's copy, fetched once)
and plans the labels beside the strip from the strip's own span and height. The
plan is a pure function, so it is run here under node against the vendored d3,
in UTC: twelve fixed dates give the labels d3.timeFormat gives, and across
spans from a day to forty years and three strip heights no two labels are
closer than the line they are drawn in.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

FRONTEND = JS_DIR.parent
TICKS = JS_DIR / "timeline-ticks.js"

HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const ctx = vm.createContext({ console });
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
process.stdout.write(JSON.stringify(vm.runInContext(process.argv[3], ctx)));
"""


def _run(expr: str):
    out = subprocess.run(
        ["node", "-e", HARNESS, str(FRONTEND / "vendor" / "d3.v7.min.js"), str(TICKS), expr],
        capture_output=True, text=True, env={**os.environ, "TZ": "UTC"},
    )
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout)


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

DAY_MS = 86_400_000


@needs_node
def test_twelve_fixed_dates_get_d3_labels_at_each_zoom():
    dates = [
        ("year", "2026-01-01", "2026"), ("year", "2019-01-01", "2019"),
        ("month", "2026-10-01", "Oct"), ("month", "2026-01-01", "2026"),
        ("month", "2025-12-01", "Dec"), ("month", "2026-03-01", "Mar"),
        ("week", "2026-10-05", "Oct 5"), ("week", "2026-10-12", "Oct 12"),
        ("week", "2026-09-28", "Sep 28"),
        ("day", "2026-10-05", "Oct 5"), ("day", "2026-10-01", "Oct 1"), ("day", "2026-10-31", "Oct 31"),
    ]
    got = _run("(" + json.dumps([[s, d] for s, d, _ in dates]) + ").map(([s, d]) => timelineTickLabel(new Date(d + 'T00:00:00'), s))")
    assert got == [label for _, _, label in dates]


@needs_node
@pytest.mark.parametrize("days", [1, 6, 14, 60, 120, 400, 1500, 2500, 15000])
@pytest.mark.parametrize("height", [240, 600, 900])
def test_no_two_labels_collide_at_any_span_or_height(days, height):
    plan = _run(
        f"timelineTickPlan({{ newest: Date.UTC(2026, 9, 18), oldest: Date.UTC(2026, 9, 18) - {days} * {DAY_MS}, width: {days} * {DAY_MS} }}, {height})"
    )
    ys = [t["y"] for t in plan["ticks"]]
    assert ys == sorted(ys), "newest at the top, ticks in order"
    assert all(0 <= y <= height for y in ys), "every label is inside the strip"
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    assert all(g >= 12 for g in gaps), f"labels closer than a line: {plan['step']} {min(gaps)}"
    assert len({t["label"] + str(t["y"]) for t in plan["ticks"]}) == len(plan["ticks"])
    if days >= 400:
        assert plan["step"] in {"month", "year"}


@needs_node
def test_the_step_widens_as_the_span_grows():
    order = {"day": 0, "week": 1, "month": 2, "year": 3}
    steps = [
        _run(f"timelineTickPlan({{ newest: Date.UTC(2026, 9, 18), oldest: Date.UTC(2026, 9, 18) - {d} * {DAY_MS}, width: {d} * {DAY_MS} }}, 600).step")
        for d in (6, 60, 400, 15000)
    ]
    assert [order[s] for s in steps] == sorted(order[s] for s in steps) and steps[0] == "day" and steps[-1] == "year"


def test_the_strip_asks_for_labels_through_a_lazy_file_and_boot_names_no_d3():
    boot = (JS_DIR / "timeline.js").read_text(encoding="utf-8")
    assert '"/js/timeline-ticks.js"' in boot, "drawTimelineScrubber asks the lazy file for the labels"
    assert "d3." not in boot, "d3 is not a boot dependency of the timeline"
    lazy = TICKS.read_text(encoding="utf-8")
    assert 'lazyScript("/vendor/d3.v7.min.js")' in lazy and 'lazyScript("/css/timeline-ticks-lazy.css")' in lazy
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert "/js/timeline-ticks.js" not in index and "timeline-ticks-lazy" not in index, "a lazy file is not a boot script"
