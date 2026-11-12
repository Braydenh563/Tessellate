"""A click on a graph note moves nothing (INBOX 587).

The owner, verbatim: "when I click nodes on the graph, it moves the graph
slightly??". d3-drag says `start` on the press, and the canvas renderer used
to pin the node, freeze the map and tell the worker a drag had begun right
there, which reheats the simulation: measured with
scratchpad/ui-sweeps/gl1005-graphclick.js on 142 notes, ten clicks moved other
notes by 15 to 65 screen px. The press now only remembers itself; the drag
begins past `GC_DRAG_THRESHOLD_PX`, and a press that never travels is a click
that tells the worker nothing (0 px after, the view unmoved).
"""

import re
from pathlib import Path
from tests._js_scope import unwrapped

CANVAS = unwrapped((Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def _handler(name: str) -> str:
    start = CANVAS.index(f'      .on("{name}", (event) => {{')
    return CANVAS[start : re.compile(r"\n      \}\);?\n").search(CANVAS, start).start()]


def test_a_press_waits_for_the_threshold_before_it_is_a_drag():
    threshold = re.search(r"^const GC_DRAG_THRESHOLD_PX = (\d+);", CANVAS, re.M)
    assert threshold and 2 <= int(threshold.group(1)) <= 5
    press = _handler("start")
    assert "gcPost" not in press and "fx" not in press and "dragNode" not in press
    move = _handler("drag")
    assert "GC_DRAG_THRESHOLD_PX" in move and "gcDragBegin(pressed, s)" in move


def test_a_click_tells_the_worker_nothing():
    release = _handler("end")
    click = release[: release.index("gcDragEnd(event, s)")]
    assert "gcClickNode" in click and "gcPost" not in click
    # The begin step is what freezes the map and reheats the worker, and only
    # the move past the threshold calls it.
    begin = CANVAS[CANVAS.index("function gcDragBegin(event, s) {") :][:6000]
    assert 'type: "drag", phase: "start"' in begin and 'type: "freeze"' in begin
    assert CANVAS.count("gcDragBegin(") == 2  # the definition and the one call
