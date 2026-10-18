"""INBOX 1300 C37: the treemap's box titles and the size of a note's dot.

The owner, 2026-10-18: "on the newest graph version, sometimes the text at the
top of the boxes gets cut off with no ellipse and the nodes are all the same
size, should they be different??". Measured on the 57-note seed before the fix
(`d2/probe.js LAYOUT=treemap`): every dot drew at 5px, because a treemap draws
no lines and the size rule counted the drawn lines; a header wider than its
box was clipped mid-letter. Now the size rule counts the notebook's links in
every layout, a header too wide ends in an ellipsis with its count kept, and
the legend says what a dot's size means.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_a_title_too_wide_for_its_box_ends_in_an_ellipsis_and_keeps_its_count() -> None:
    script = _function(CANVAS, "gcEllipsize") + """
const measure = (t) => t.length * 7;
console.log(JSON.stringify({
  fits: gcEllipsize("Work", " (10)", 200, measure),
  cut: gcEllipsize("Courses & Study", " (10)", 90, measure),
  bare: gcEllipsize("Courses & Study", " (10)", 20, measure),
}));
"""
    out = _run(script)
    assert out["fits"] == "Work (10)"
    assert out["cut"].endswith("… (10)") and len(out["cut"]) * 7 <= 90, out["cut"]
    assert out["cut"].startswith("Cour")
    # No room for even a letter and the count: nothing, never a clipped glyph.
    assert out["bare"] == ""


def test_the_treemap_header_is_ellipsized_not_clipped() -> None:
    body = _function(CANVAS, "gcDrawTreemap")
    assert "gcEllipsize(" in body
    assert "ctx.clip()" not in body, "a clip cuts a letter in half with no ellipsis"


def test_a_treemap_dot_is_sized_by_its_links_not_by_the_lines_drawn() -> None:
    # The treemap draws no lines (`layoutTreemap` returns none), so a degree
    # read off the drawn lines was 0 for every note: one size for all.
    at = CANVAS.index("node.r = gcRadius(")
    block = CANVAS[at - 1200 : at + 200]
    assert "linkDegree" in block, "the size rule must count the notebook's links"


def test_the_legend_says_what_a_dots_size_means() -> None:
    body = _function(CANVAS, "gcLegendSizeKey")
    assert "GC_SIZE_KEY[graphSizeMode()]" in body
    table = CANVAS[CANVAS.index("const GC_SIZE_KEY") :][:300]
    for words in ("more links", "longer note", "edited more recently"):
        assert words in table
    assert "gcLegendSizeKey(" in CANVAS.replace(body, ""), "the key is built on every render"
    # The help panel says it too (standing order 13).
    help_panel = HTML[HTML.index('id="graph-help-panel"') :][:3200]
    assert "bigger dot" in help_panel.lower()


def test_a_computed_layout_does_not_ring_every_dot_as_held() -> None:
    # Treemap, tree, radial and arc set fx on every note; the ring test read
    # that as held and drew the fallback accent ring on all of them.
    assert '(node.fx != null && s.layoutKind === "force")' in CANVAS
