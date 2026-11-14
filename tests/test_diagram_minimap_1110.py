"""W18 R15 (s9b-1110): a corner minimap for a diagram that overflows its stage.

Measured first (1440 x 900, Fit, the 24 bundled templates): 12 overflow the stage by 24 to 313 px, so "a diagram routinely
overflows" holds. The pure half runs under node; the DOM half is read for what it must hold. The rects at 1440 and 390 are
in docs/roadmap/HISTORY.md.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
SRC = (JS / "diagram-minimap.js").read_text(encoding="utf-8")
VIEW = (JS / "diagram-view.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-minimap.js'))},'utf8'),ctx);"
        f"const m=ctx.diagramModel.minimap.math;console.log(JSON.stringify({expr}));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@needs_node
def test_the_thumbnail_keeps_the_drawings_proportions_within_its_longest_side() -> None:
    assert _run("m.thumb({w: 1000, h: 500})") == {"w": 120, "h": 60}
    assert _run("m.thumb({w: 300, h: 900})") == {"w": 40, "h": 120}


@needs_node
def test_it_shows_only_when_the_picture_is_larger_than_the_pane() -> None:
    assert _run("m.over({w: 783, h: 479}, {w: 783, h: 479})") is False
    # One pixel of rounding is not an overflow.
    assert _run("m.over({w: 784, h: 480}, {w: 783, h: 479})") is False
    assert _run("m.over({w: 881, h: 479}, {w: 783, h: 479})") is True
    assert _run("m.over({w: 783, h: 733}, {w: 783, h: 420})") is True


@needs_node
def test_the_window_is_the_part_of_the_picture_in_view() -> None:
    # A 2000 x 1000 picture at the origin of a 500 x 250 pane, scrolled to (500, 250): a quarter wide, a quarter tall.
    got = _run("m.window({x: 0, y: 0, w: 2000, h: 1000}, {left: 500, top: 250, w: 500, h: 250})")
    assert got == {"x": 0.25, "y": 0.25, "w": 0.25, "h": 0.25}
    # A picture that fits one way fills the window that way, never over 1.
    assert _run("m.window({x: 0, y: 0, w: 400, h: 1000}, {left: 0, top: 0, w: 500, h: 250})") == {"x": 0, "y": 0, "w": 1, "h": 0.25}


@needs_node
def test_a_press_centres_the_pane_on_that_spot_and_stays_inside_the_picture() -> None:
    mid = _run("m.scrollFor({x: 0, y: 0, w: 2000, h: 1000}, {w: 500, h: 250}, 0.5, 0.5)")
    assert mid == {"left": 750, "top": 375}
    assert _run("m.scrollFor({x: 0, y: 0, w: 2000, h: 1000}, {w: 500, h: 250}, 0, 0)") == {"left": 0, "top": 0}
    assert _run("m.scrollFor({x: 0, y: 0, w: 2000, h: 1000}, {w: 500, h: 250}, 1, 1)") == {"left": 1500, "top": 750}


def test_the_view_asks_for_it_once_and_the_file_makes_a_plain_corner_dock() -> None:
    assert "diagram-minimap.js" in VIEW and "diagramModel.minimap" in VIEW
    assert 'className = "dock dgm-minimap hidden"' in SRC
    assert "data-dock-name" not in SRC and "dockName" not in SRC
    assert "pointerdown" in SRC and "setPointerCapture" in SRC
    # Hidden by the rule until the picture overflows, and on a phone, where a finger pans and the zoom bar has its own row.
    assert ".dgm-minimap.hidden" in CSS or ".dgm-minimap[hidden]" in CSS


def test_the_minimap_sits_in_the_corner_the_other_controls_leave_free() -> None:
    rule = CSS[CSS.index(".dgm-minimap {") : CSS.index("}", CSS.index(".dgm-minimap {"))]
    assert "position: absolute" in rule
    assert "inset-block-end: var(--space-5)" in rule and "inset-inline-start: var(--space-5)" in rule
    assert "var(--modal-bg)" in rule and "var(--shadow-md)" in rule
    assert "px" not in rule.replace("1px solid", "")



def test_the_overview_lifts_above_the_sideways_offer():
    """INBOX 1737 (owner screenshot): the overview lay over "This chart is tall for this pane." in the same bottom-left
    corner. While the offer shows, diagram-outline.js raises the overview by the offer's height; kept, turned or hidden,
    the inline inset is cleared. On a phone the offer is absolute at the top, so the overview keeps its corner."""
    outline = (JS / "diagram-outline.js").read_text(encoding="utf-8")
    assert 'querySelector(":scope > .dgm-minimap")' in outline and "lift(true)" in outline and outline.count("lift(false)") == 2
    assert 'getComputedStyle?.(S.sideways).position !== "absolute"' in outline
    assert "map.style.insetBlockEnd = below ?" in outline


def test_a_scroll_moves_the_frame_with_a_transform_and_reads_no_layout():
    """L-documents-89: the scroll listener re-measured the picture and wrote left, top, width and height on every scroll
    event of a pan (a forced layout each frame, 1440 only: a phone hides the overview). It now measures on a zoom and a
    resize and moves the frame by a transform on a scroll."""
    text = (ROOT / "frontend" / "js" / "diagram-minimap.js").read_text(encoding="utf-8")
    assert 'fig.addEventListener("scroll", pan, { passive: true })' in text
    pan = text[text.index("const pan = ") : text.index("//: Press, and drag")]
    for forbidden in ("offsetWidth", "offsetLeft", "scrollWidth", "getBoundingClientRect", ".style.left", ".style.top", "place("):
        assert forbidden not in pan, forbidden
    assert "translate(" in pan
