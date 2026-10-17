"""The graph's first visible frame is drawn at the fitted zoom (INBOX 738).

The owner: "the graph always loads in really zoomed in before it rights itself
with the fitted zoom". Measured on 60 notes (scratchpad/ui-sweeps/
graphdepth2.js graphfirstframe, every animation frame's zoom and the canvas opacity):
the first visible frame was at k 1.21, the worst at k 2.5 (the fit's clamp),
against a settled fit of 0.79, and 104 visible frames were more than 10% off
it. Three causes, three fixes, checked here:

- the first fit read `x`/`y`, which were still the starting spiral until the
  next paint's glide; it now snaps the glide first (`gcGlideFinish`);
- the first fit glided from the default camera over 500 ms while the canvas
  was fading in; it is applied at once while the canvas is hidden;
- one tick out of the spiral is not the map's shape: a fresh layout is
  stepped in the worker, unposted, until it is as cool as the settle fit
  wants or a budget is spent (`WARM_MS`).

After: first visible frame k 0.785 against 0.788, no frame 10% off. The arc
(k 0.31) started at k 1 for a frame; `frameTree` is instant from the default
camera too.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
HARNESS = ROOT / "tests" / "_graph_worker_harness.js"
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")
GRAPH = (JS / "graph.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _scenario(warm: bool) -> dict:
    # Fifteen notes: the warm-up is budgeted in wall time, and a small map
    # cools inside it many times over even on a box shared with a test run.
    nodes = [{"id": i, "group": f"g{i % 3}", "r": 7} for i in range(15)]
    edges = [{"source": i, "target": (i // 5) * 5, "kind": "link"} for i in range(15) if i % 5]
    return {"nodes": nodes, "edges": edges, "ticks": 3, "warm": warm}


def _first_alpha(scenario: dict) -> float:
    out = subprocess.run(
        ["node", str(HARNESS)], input=json.dumps(scenario), capture_output=True, text=True, check=True, timeout=60
    ).stdout
    return json.loads(out)["firstAlpha"]


@needs_node
def test_a_warmed_layout_posts_its_first_tick_already_cool():
    assert _first_alpha(_scenario(warm=True)) <= 0.08


@needs_node
def test_an_unwarmed_layout_still_posts_from_full_heat():
    # Every other init (a filter change, a drag's reheat) is unchanged.
    assert _first_alpha(_scenario(warm=False)) > 0.9


def _block(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_the_first_fit_snaps_the_glide_and_is_instant():
    first = _block(CANVAS, "if (!s.fittedOnce) {", "gcReveal(s);")
    assert "gcGlideFinish(s);" in first
    assert re.search(r"fitGraphToView\([^)]*, true\)", first)


def test_warm_is_asked_for_whenever_the_map_is_framed_again():
    # Round 2 of INBOX 775: a map already showing is not hidden to re-layout;
    # the warm-up is played back from where its notes stood
    # (tests/test_graph_feel_775.py).
    assert "warm: reframe && !restoring && !(viewSeed && viewSeed.alpha === 0)," in CANVAS


def test_an_instant_fit_is_applied_now_not_as_a_zero_length_transition():
    for name in ("fitGraphToView", "frameTree"):
        start = GRAPH.index(f"\nfunction {name}(")
        body = GRAPH[start : GRAPH.index("\n}\n", start)]
        assert "if (instant)" in body and "svg.interrupt().call(zoomBehavior.transform, framed);" in body, name


def test_a_map_framed_for_a_box_never_measured_is_reframed_at_once_not_glided():
    """Owner 2026-10-12, "it shifts or glitches in". Measured (400 notes,
    1440x900, every fit logged): the map is first drawn while its tab is
    hidden, framed for the 800x540 fallback (`gcResize`, "a box never
    measured"); opening the tab fired the resize observer, whose refit
    glided the camera from k 0.53 to 0.68 and 234 px across, in view. A box
    that was never really measured is reframed at once, before the paint."""
    resize = CANVAS[CANVAS.index("function gcResize(") : CANVAS.index("function gcEnsureCanvas(")]
    assert "s.dimsReal = " in resize
    observer = CANVAS[CANVAS.index("s.observer = new ResizeObserver(") :][:1600]
    assert "const wasReal = s.dimsReal !== false;" in observer
    assert "s.dims.w, s.dims.h, !wasReal)" in observer
