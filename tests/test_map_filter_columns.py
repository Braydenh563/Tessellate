"""Decision 34 extended (MINDMAP_PLAN): Filter by marker takes several at once
and the topic's labels (its tags), and the outline shows each topic's markers,
due day and labels as cells. The pure region (`WB-MAP-FILTER-BEGIN` to `-END`)
runs in node here; the popover and the outline cells are driven in a browser.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def _run(expr: str) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    parts = MAP_JS[MAP_JS.index("const WB_MAP_MARKER_ICONS") : MAP_JS.index("function wbMapPaintMarkers")]
    region = MAP_JS[MAP_JS.index("// WB-MAP-FILTER-BEGIN") : MAP_JS.index("// WB-MAP-FILTER-END")]
    script = "const wbMarkerUi = {};\n" + parts + region + f"\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_labels_are_filter_keys_beside_the_markers():
    keys = _run('wbMapMarkerKeys({ flag: true, labels: ["Urgent", " ", "home"] })')
    assert keys == ["flag", "t:Urgent", "t:home"]


def test_several_filters_light_a_topic_that_carries_any_of_them():
    node = '{ priority: 1, labels: ["home"] }'
    assert _run(f"wbMarkerUi.match.lit(wbMapMarkerKeys({node}), new Set(['p1', 'flag']))") is True
    assert _run(f"wbMarkerUi.match.lit(wbMapMarkerKeys({node}), new Set(['t:home']))") is True
    assert _run(f"wbMarkerUi.match.lit(wbMapMarkerKeys({node}), new Set(['flag', 'done']))") is False
    assert _run(f"wbMarkerUi.match.lit(wbMapMarkerKeys({node}), new Set())") is True


def test_the_bar_names_every_filter_chosen():
    assert _run("wbMarkerUi.match.words(new Set(['p1', 't:home', 'flag']))") == "Priority 1, home, Flagged"
    assert _run("wbMarkerUi.match.words(new Set(['p1', 't:a', 't:b', 'flag', 'done']))") == "Priority 1, a, b and 2 more"


def test_a_filter_toggles_and_the_filter_is_a_set_not_one_key():
    assert "filters: new Set()" in MAP_JS
    assert "wbMarkerUi.filter " not in MAP_JS and "wbMarkerUi.filter)" not in MAP_JS


def test_the_outline_row_has_a_cell_for_markers_and_one_for_labels():
    row = MAP_JS[MAP_JS.index("function wbOutlineRowEl") : MAP_JS.index("function wbOutlineEditing")]
    assert "wb-outline-marks" in row and "wb-outline-tags" in row
    assert "wbMarkerUi.match.cells(" in MAP_JS[MAP_JS.index("function wbOutlineSync") : MAP_JS.index("function wbOutlineRowOf")]
