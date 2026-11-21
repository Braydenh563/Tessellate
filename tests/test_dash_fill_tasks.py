"""Each dashboard widget fills in its own task, and the skeleton follows without a timer read (L701).

Measured at 4x CPU on the 500-note budget notebook: the grid loop's continuation ran every widget's
render in one microtask checkpoint (renderDashboard resolve-promise 56 ms), and `dashSkeletonFollowTask`
read `grid.offsetTop` every 80 ms while the cards were dirtying layout (36 to 44 ms a read, each a
forced layout). These pin the structure under node, so a busy machine cannot skew them.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")


YIELD = DASH[DASH.index("mountWidgetBody.yield = "):].split("\n", 1)[0]


def _fn(name: str) -> str:
    start = DASH.index(f"function {name}(")
    return DASH[start : DASH.index("\n}\n", start) + 3]


def test_widgets_render_one_per_task() -> None:
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = f"""
let task = 0;
globalThis.scheduler = {{ yield: () => new Promise((r) => setImmediate(() => {{ task++; r(); }})) }};
globalThis.showSkeletons = () => {{}};
globalThis.clearSkeletons = () => {{}};
globalThis.MutationObserver = class {{ observe() {{}} disconnect() {{}} }};
globalThis.smallButton = () => ({{}});
const WIDGET_STALL_MS = 20000;
{_fn("mountWidgetBody")}
{YIELD}
const body = () => ({{ isConnected: true, children: [], querySelector: () => null, replaceChildren() {{}} }});
const at = [];
const widget = (n) => ({{ render: () => at.push([n, task]) }});
(async () => {{
  const all = [1, 2, 3, 4].map((n) => mountWidgetBody(widget(n), body()));
  const sync = at.length;
  await Promise.all(all);
  console.log(JSON.stringify({{ sync, at }}));
  process.exit(0);
}})();
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout
    got = json.loads(out)
    assert got["sync"] == 0, "no render runs inside the loop that mounts the bodies"
    tasks = [t for _, t in got["at"]]
    assert len(set(tasks)) == len(tasks) == 4, f"each widget's render starts in its own task: {tasks}"


def test_the_grid_loop_and_fills_share_one_yield() -> None:
    assert "const dashYield = mountWidgetBody.yield;" in DASH.split("async function renderDashboard(", 1)[1]
    assert re.search(r"mountWidgetBody\.yield\(\)\s*\.then\(\(\) => widget\.render\(body\)\)", _fn("mountWidgetBody"))
    assert "Promise.resolve()\n    .then(() => widget.render(body))" not in DASH


def test_the_skeleton_follows_by_the_grids_observer_not_a_timer_read() -> None:
    body = DASH.split("function dashFillingSkeleton(", 1)[1].split("\nfunction dashFillingSkeletonDone", 1)[0]
    assert "dashSkeletonFollowTask" not in body and "setTimeout" not in body and "new ResizeObserver" not in body
    # The read is in a function the grid's own observer calls, after the frame's layout: it forces nothing.
    assert "ro.follow = () => {" in body and "grid.offsetTop" in body.split("ro.follow = () => {", 1)[1]
    watch = _fn("watchDashWidgets")
    assert "dashResizeObserver.follow?.();" in watch
    done = _fn("dashFillingSkeletonDone")
    assert "follow = null;" in done and "unobserve(el)" in done


def test_sizing_uses_the_observers_heights_and_no_frame_hop() -> None:
    """L-world-class-620: the sizing callback read every card's rect after the fills had dirtied layout."""
    watch = _fn("watchDashWidgets")
    cb = watch.split("new ResizeObserver((entries) => {", 1)[1].split("\n  });", 1)[0]
    assert "sizeDashWidgets.heights.set(" in cb and "borderBoxSize" in cb
    assert "getBoundingClientRect" not in cb and "requestAnimationFrame" not in cb
    sizing = _fn("sizeDashWidgets")
    assert "known.get(card) ?? card.getBoundingClientRect().height" in sizing
    assert "sizeDashWidgets.heights = new WeakMap();" in DASH
