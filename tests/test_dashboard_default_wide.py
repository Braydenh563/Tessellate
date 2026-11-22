"""A widget that starts wide must be able to go narrow (the heatmap's Narrow
button once saved an empty list that read as "never chosen")."""

import re
from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")


def test_every_default_wide_widget_is_a_real_widget_shown_by_default():
    wide = re.search(r"const DASH_DEFAULT_WIDE = \[([^\]]*)\]", JS).group(1)
    shown = re.search(r"const DASH_DEFAULT_SHOWN = \[([^\]]*)\]", JS, re.S).group(1)
    for name in re.findall(r'"([\w-]+)"', wide):
        assert f'  {name}: {{' in JS or f'"{name}": {{' in JS, name
        assert f'"{name}"' in shown, f"{name} starts wide but is not shown by default"


def test_narrowing_is_remembered_so_the_default_does_not_come_back():
    toggle = JS.split("async function toggleDashWidgetWide", 1)[1].split("\n}\n", 1)[0]
    assert "next.narrow" in toggle
    assert ".filter((n) => !(saved.narrow || []).includes(n))" in JS


def test_a_fresh_dashboard_shows_only_widgets_that_can_be_acted_on():
    """L-world-class-121 (decision 51): the four display-only widgets (stats,
    streak, heatmap, pace) either stay behind Customise or carry a button into
    Statistics. Measured 2026-11-21 on a fresh notebook, 1440x900: all 11
    default widgets hold 1 to 3 controls; the other 18 start hidden."""
    shown = re.search(r"const DASH_DEFAULT_SHOWN = \[([^\]]*)\]", JS, re.S).group(1)
    for name in ("stats", "streak", "pace"):
        assert f'"{name}"' not in shown
    assert '"heatmap"' in shown and 'dashStatsButton("heatmap-statistics")' in JS
