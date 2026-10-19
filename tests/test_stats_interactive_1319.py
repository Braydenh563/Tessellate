"""INBOX 1319: the Statistics charts answer the pointer and the keyboard.

The pure parts of the Ask chart recipe (tooltip words, arrow-key stepping, the
drawn width) are run in node; the wiring is checked in the source, and the
measured side (hover, focus, click) is `scratchpad/ui-sweeps/stats1319.js`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHART = (ROOT / "frontend" / "js" / "ask-chart.js").read_text(encoding="utf-8")
STATS = (ROOT / "frontend" / "js" / "statistics.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "utilities-lazy.css").read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def _node(prelude: str, expr: str):
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    done = subprocess.run(
        [node, "-e", f"{prelude}\nprocess.stdout.write(JSON.stringify({expr}));"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_tooltip_says_the_period_and_the_exact_value():
    prelude = _fn(CHART, "askChartTipText")
    got = _node(
        prelude,
        """[
          askChartTipText({by: "month"}, {label: "2026-03", value: 12}),
          askChartTipText({by: "month"}, {label: "2026-03", value: 1}),
          askChartTipText({by: "feature", unit: ["use", "uses"]}, {label: "Notes tab", value: 1234}),
          askChartTipText({by: "day"}, {label: "2026-10-05", value: 0}),
        ]""",
    )
    assert got[0].startswith("March 2026") and got[0].endswith(": 12 notes")
    assert got[1].endswith(": 1 note")
    assert got[2] == "Notes tab: 1,234 uses"
    assert "5 October 2026" in got[3] or "October 5, 2026" in got[3]
    assert got[3].endswith(": 0 notes")


def test_arrow_keys_walk_the_points_and_stop_at_the_ends():
    prelude = _fn(CHART, "askChartStep")
    got = _node(
        prelude,
        """[
          askChartStep(2, "ArrowRight", 5), askChartStep(2, "ArrowLeft", 5),
          askChartStep(4, "ArrowRight", 5), askChartStep(0, "ArrowLeft", 5),
          askChartStep(2, "Home", 5), askChartStep(2, "End", 5), askChartStep(2, "x", 5),
        ]""",
    )
    assert got == [3, 1, 4, 0, 0, 4, 2]


def test_the_drawn_width_follows_the_card_within_bounds():
    prelude = "const ASK_CHART_W = 640;" + _fn(CHART, "askChartWidth")
    assert _node(prelude, "[askChartWidth(0), askChartWidth(100), askChartWidth(1000), askChartWidth(5000)]") == [640, 320, 1000, 1400]


def test_the_chart_marks_are_focusable_and_act_on_click():
    svg = _fn(CHART, "askChartSvg")
    assert "tabindex" in svg and "ask-chart-pt" in svg and "ask-chart-hit" in svg
    wire = _fn(CHART, "askChartWire")
    assert "ResizeObserver" in wire and "onPick" in wire and "ask-chart-tip" in wire and "askChartStep" in wire
    assert "askChartWire(host, chart)" in _fn(CHART, "drawAskChart")
    assert "ArrowRight" in CHART
    # the rule is opt-in, so the Ask box's chart is unchanged
    assert "chart.interactive" in svg


def test_the_statistics_page_opts_in_and_styles_the_tooltip():
    assert "interactive: true" in STATS
    for selector in (".stats-chart", ".ask-chart-tip", ".ask-chart-pt:focus-visible"):
        assert selector in CSS


def test_a_click_acts_and_the_card_closes_first():
    go = _fn(STATS, "statsGo")
    assert go.index("statsCard.close") < go.index("await go()")
    assert "timelineJumpToDay" in _fn(STATS, "statsOpenMonth")
    assert "switchTab" in _fn(STATS, "statsOpenFeature")
    assert "onPick: statsOpenMonth" in STATS


def test_tiles_open_what_they_count_and_the_range_asks_the_server():
    tile = _fn(STATS, "statsTile")
    assert '"button"' in tile and "statsGo(go)" in tile
    notebook = _fn(STATS, "statsNotebookSection")
    for tab in ('statsOpenTab("notes")', 'statsOpenTab("library")', 'statsOpenTab("graph")', "statsOpenLooseEnds"):
        assert tab in notebook
    reminders = _fn(STATS, "statsRemindersSection")
    assert 'open("all")' in reminders and 'open("done")' in reminders and 'open("open")' in reminders
    ranges = _fn(STATS, "statsRangeControl")
    assert "/statistics?growth=" in ranges and 'select.id = "stats-range"' in ranges
    assert all(f'["{v}"' in STATS for v in ("12", "3", "all"))


def test_each_week_row_has_a_small_line_of_its_days():
    week = _fn(STATS, "statsWeekCard")
    assert "statsSpark(" in week and "week.daily" in week
    assert ".stats-spark-this" in CSS and ".stats-spark-last" in CSS
