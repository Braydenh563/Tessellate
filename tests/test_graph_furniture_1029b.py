"""Audit 1029 rank 57 (G9, G22, G23, G24): the graph's furniture.

Measured at 1440x900 with `/tmp/claude-0/graphb/f57.js` (session scratch), on
36 notes in 6 categories plus 16 more categories:

- the legend was one row that scrolled: 17 entries, scrollWidth 2088 against
  1308, 5 of them out of sight (G9);
- the Filter fold showed one chip, "No kind 64", a count of a thing with
  nothing to filter (G22);
- the Help panel was 1,296 characters in three paragraphs and scrolled
  (568 in 510) (G23);
- with Trace open, the minimap and the Trace strip overlapped by 8,861 px²
  (G24).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")
BOOT_CSS = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("0*.css")))

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\n(?:async )?function {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str):
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_the_legend_wraps_to_two_rows_and_scrolls_past_them() -> None:
    rule = re.search(r"\.graph-legend-row #graph-legend \{(.*?)\}", LAZY, re.S).group(1)
    assert "flex-wrap: wrap" in rule and "overflow-y: auto" in rule and "max-height: 5.2em" in rule
    assert "overflow-x: hidden" in rule
    assert not re.search(r"^#graph-legend \{[^}]*nowrap", BOOT_CSS, re.M | re.S), "the one-row rule is gone from boot CSS"


@needs_node
def test_a_link_kind_row_is_drawn_only_when_there_is_a_kind_to_filter() -> None:
    script = (
        _function(CANVAS, "gcLinkKindRows")
        + """
        const edge = (link_type, type_name) => ({ kind: "link", link_type, type_name });
        const keys = (edges) => gcLinkKindRows(edges).map((r) => r[0]);
        console.log(JSON.stringify({
          none: keys([]),
          untypedOnly: keys([edge(null), edge(null)]),
          typed: keys([edge(null), edge("cites", "Cites"), edge("cites", "Cites")]),
          threads: keys([{ kind: "thread" }]),
          offAndUntyped: gcLinkKindRows([edge(null)], new Set(["untyped"])).map((r) => r[0]),
        }));
        """
    )
    out = _run(script)
    assert out["none"] == [] and out["untypedOnly"] == [] and out["threads"] == []
    assert out["offAndUntyped"] == ["untyped"], "a kind turned off keeps its chip: it is the only way back"
    assert out["typed"] == ["cites", "untyped"], "the biggest kind first, and No kind stays once there is a kind to tell it from"
    body = _function(CANVAS, "gcRenderFilterChips")
    assert "gcLinkKindRows(data.edges, graphHiddenLinkKinds)" in body
    assert "No link has a kind yet." in body


def test_the_help_panel_is_short_lines_that_fit_without_scrolling() -> None:
    panel = HTML[HTML.index('id="graph-help-panel"') :]
    panel = panel[: panel.index("</div>")]
    text = re.sub(r"\s+", " ", re.sub(r"<!--.*?-->|<[^>]+>", " ", panel, flags=re.S)).strip()
    assert len(text) <= 1000, len(text)
    items = re.findall(r"<li>(.*?)</li>", panel, re.S)
    assert len(items) >= 5
    for item in items:
        words = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", item)).strip()
        assert len(words) <= 190, words
    for phrase in ("Hover a note", "dates", "Drop one note onto another", "Trace", "bigger dot", "Treemap", "mind map"):
        assert phrase in text or phrase.lower() in text.lower(), phrase


@needs_node
def test_the_minimap_clears_the_trace_strips_by_one_measured_offset() -> None:
    script = (
        _function(GRAPH, "graphRailOffset")
        + """
        const strip = (top, bottom) => ({ top, bottom });
        console.log(JSON.stringify({
          none: graphRailOffset([], 112),
          hidden: graphRailOffset([strip(0, 0), strip(0, 0)], 112),
          trace: graphRailOffset([strip(124, 174), strip(0, 0)], 112),
          both: graphRailOffset([strip(124, 174), strip(182, 217)], 112),
        }));
        """
    )
    assert _run(script) == {"none": 0, "hidden": 0, "trace": 62, "both": 105}


def test_the_minimap_top_corners_start_below_the_rail() -> None:
    rule = re.search(r"\.graph-minimap-tl,\s*\.graph-minimap-tr \{(.*?)\}", BOOT_CSS, re.S).group(1)
    assert "top: var(--graph-chrome-top);" in rule
    assert "--graph-rail-h" not in BOOT_CSS, "no new custom property: the count only falls"
    wiring = _function(GRAPH, "initGraphRailToken")
    assert 'setProperty("--graph-chrome-top"' in wiring and 'removeProperty("--graph-chrome-top")' in wiring
    assert "ResizeObserver" in wiring
    assert "initGraphRailToken();" in GRAPH
