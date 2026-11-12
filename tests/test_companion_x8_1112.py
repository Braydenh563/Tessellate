"""X8 (W14, in-app companion): the large view's fit asks a part for its style only when the part reaches past what is already
counted. Same margins as asking every part (a node harness with a fake figure), a fraction of the style reads."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
MENU = unwrapped((ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8"))


def _fit_src() -> str:
    start = MENU.index("function nameMarkViewerFit(")
    return MENU[start : MENU.index("\n}\n", start) + 2]


HARNESS = r"""
class SVGElement {}
class SVGGElement extends SVGElement {}
class SVGSVGElement extends SVGElement {}
let styleReads = 0;
const getComputedStyle = (el) => { styleReads += 1; return el.cs; };
const part = (r, cs = { visibility: "visible", display: "inline", opacity: "1" }) => {
  const el = new SVGElement();
  el.children = []; el.cs = cs;
  el.closest = () => null;
  el.getBoundingClientRect = () => ({ left: r[0], top: r[1], right: r[2], bottom: r[3], width: r[2] - r[0], height: r[3] - r[1] });
  return el;
};
const parts = JSON.parse(process.argv[1]).map((p) => part(p.r, p.cs));
const figure = {
  isConnected: true, style: {},
  getBoundingClientRect: () => ({ left: 100, top: 100, right: 164, bottom: 192, width: 64, height: 92 }),
  querySelectorAll: () => parts,
};
"""


def _run(rects: list[dict]) -> dict:
    script = HARNESS + _fit_src() + "\nnameMarkViewerFit(figure);\nconsole.log(JSON.stringify({ style: figure.style, styleReads }));"
    out = subprocess.run(["node", "-e", script, json.dumps(rects)], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_parts_inside_the_box_cost_no_style_read_and_the_margins_are_unchanged() -> None:
    inside = [{"r": [110 + i % 40, 110 + i % 60, 150 + i % 10, 180 - i % 20]} for i in range(300)]
    tail = {"r": [120, 150, 140, 230]}  # a tail hanging 38 px below the box
    hat = {"r": [110, 80, 150, 100]}  # a hat 20 px above it
    r = _run(inside + [tail, hat])
    assert r["style"] == {"marginTop": "20px", "marginBottom": "38px"}  # nothing grows sideways
    assert r["styleReads"] == 2  # only the two parts that reach out were asked, of 302


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_hidden_part_that_reaches_out_still_does_not_count() -> None:
    ghost = {"r": [120, 150, 140, 260], "cs": {"visibility": "hidden", "display": "inline", "opacity": "1"}}
    faint = {"r": [120, 150, 140, 260], "cs": {"visibility": "visible", "display": "inline", "opacity": "0"}}
    r = _run([ghost, faint])
    assert r["style"] == {} and r["styleReads"] == 2


def test_the_fit_still_reads_nothing_it_did_not_before() -> None:
    body = _fit_src()
    assert body.count("getComputedStyle(") == 1 and body.count("getBoundingClientRect()") == 2
    assert "r.top >= top && r.bottom <= bottom && r.left >= left && r.right <= right" in body
