"""Pie charts for the dashboard (L-world-class-179). The chart recipe
(DESIGN.md "A chart answering a question", ask-chart.js) gains kind "pie", and
the dashboard's Category mix widget draws the category counts with it.
Measured in the app (scratchpad sweep pie.js, a 340 px widget, eight
categories): six slices (five and "Other"), labels "Work: 9 notes, 20%", 0
legend names cut and 0 overlapping, the legend in the ink colour at 12 px."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
        if depth == 0:
            return src[start:i]


@needs_node
def test_a_pie_keeps_five_slices_and_folds_the_rest_into_other():
    chart = frontend_text("ask-chart.js")
    rows = [{"label": f"C{i}", "value": v} for i, v in enumerate([3, 9, 0, 7, 1, 5, 2, 8])]
    script = "const ASK_PIE_SLICES = 6;\n" + _function(chart, "askChartPieRows") + f"\nprocess.stdout.write(JSON.stringify(askChartPieRows({json.dumps(rows)})));"
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert [r["label"] for r in out] == ["C1", "C7", "C3", "C5", "C0", "Other"]
    assert out[-1]["value"] == 3 and out[-1]["other"] is True
    assert sum(r["value"] for r in out) == sum(r["value"] for r in rows)


def test_the_pie_is_the_chart_recipe_not_a_second_chart():
    chart = frontend_text("ask-chart.js")
    assert 'if (chart.kind === "pie") return askChartPieSvg(chart, width);' in _function(chart, "askChartSvg")
    pie = _function(chart, "askChartPieSvg")
    assert '"ask-chart-pt"' in pie and "aria-label" in pie and "#" not in re.sub(r"`[^`]*`", "", pie).replace("//:", "")
    css = (ROOT / "frontend/css/03-dashboard-widgets.css").read_text(encoding="utf-8")
    for rule in (".ask-chart-slice {", ".ask-chart-slice.is-other {", ".ask-chart-legend {"):
        assert rule in css, rule


def test_the_category_mix_widget_is_on_the_dashboard_and_findable():
    dash = frontend_text("dashboard.js")
    assert re.search(r"\bmix: \{ title: \"ph:chart-pie Category mix\"", dash)
    assert "mix: \"notes\"" in dash
    assert "render: (body) => renderCategoriesWidget(body, true)" in dash
    body = _function(dash, "renderCategoriesWidget")
    assert 'kind: "pie"' in body and "drawAskChart(host" in body and "categoryDotColour(name)" in body
    assert '"widget-mix"' in frontend_text("reveal-targets.js")
    assert 'reveal: "widget-mix"' in frontend_text("app-features.js")
