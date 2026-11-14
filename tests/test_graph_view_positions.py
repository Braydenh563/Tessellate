"""GRAPH_PLAN Phase 5, "positions on a saved view" (INBOX 275's neighbour
row, "Placed from INBOX, 2026-09-21").

A saved view used to restore the layout, the colour rule, the filters, the
groups and the zoom transform, but not where the unpinned notes sat, so a
force-layout view reopened as a fresh solution of the same forces rather
than the picture that was saved. Measured live with
`scratchpad/ui-sweeps/graphviewpos.js` (needs a running app; this file is
the static guard the Python suite can run on its own).

The fix is the one on record: `graphCaptureView` (frontend/js/graph.js) stores
each visible node's x/y, and `renderGraphCanvas` (frontend/js/graph-canvas.js,
the default renderer; the SVG one is a dev-only fallback slated for
deletion) seeds the simulation with them. The decision made alongside it,
2026-09-21: a restored arrangement holds, it does not re-settle, and only
reheats (holding the saved notes fixed while it does) when a note has no
saved position (added since the view was saved). This is a shape check, not
a behaviour one: it cannot run the simulation, so a change that keeps every
string here but flips the actual logic (e.g. hands the "no unplaced" branch
alpha 1) would still pass. The sweep is what catches that.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._js_scope import gc_worker, unwrapped

GRAPH = Path(__file__).resolve().parents[1] / "frontend" / "js" / "graph.js"
GRAPH_CANVAS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "graph-canvas.js"


def _text(path: Path) -> str:
    return unwrapped(path.read_text(encoding="utf-8"))


def test_a_saved_view_captures_node_positions():
    source = _text(GRAPH)
    capture = re.search(r"(?s)function graphCaptureView\(\).*?\n\}", source)
    assert capture, "graphCaptureView not found in graph.js"
    body = capture.group(0)
    assert "positions:" in body, (
        "graphCaptureView must store each visible node's x/y (GRAPH_PLAN "
        "Phase 5), not only the layout/colour/filters/groups/transform it "
        "already captured"
    )
    assert "graphNodesRef" in body.split("positions:")[1][:400], (
        "the captured positions must come from graphNodesRef, the live node "
        "array either renderer draws from, not a stale copy"
    )


def test_applying_a_saved_view_stages_its_positions():
    source = _text(GRAPH)
    apply = re.search(r"(?s)function graphApplyView\(view\) \{.*?\n\}", source)
    assert apply, "graphApplyView not found in graph.js"
    assert "graphPendingViewPositions" in apply.group(0), (
        "graphApplyView must stage view.positions somewhere renderGraphCanvas "
        "can pick it up; the one-shot global renderGraphCanvas reads is gone"
    )


def test_the_canvas_renderer_seeds_from_a_restored_view_and_holds_it():
    """The decision made 2026-09-21: a restored arrangement holds, it does
    not re-settle, and only reheats for a note the view never saved, fixing
    the saved ones while that reheat runs."""
    source = _text(GRAPH_CANVAS)
    render = re.search(r"(?s)async function renderGraphCanvas\(s = gcTab\) \{.*?\n\}\n", source)
    assert render, "renderGraphCanvas not found in graph-canvas.js"
    body = render.group(0)
    assert "graphPendingViewPositions" in body, (
        "renderGraphCanvas must consume the positions graphApplyView stages"
    )
    # One-shot: read once, then cleared, so a second render triggered by the
    # same graphApplyView call (it fires one per control it restores) does
    # not re-seed on top of a layout that has already moved on.
    assert body.count("graphPendingViewPositions = null") >= 1
    assert "unplacedByView" in body, (
        "must distinguish a note the view saved from one added since: only "
        "the latter may make the restore reheat"
    )
    assert "gcStartWorker(" in body and "alpha:" in body and "freezeIds:" in body, (
        "the alpha (0 to start at rest, 1 to reheat) and which ids to hold "
        "while it does must reach gcStartWorker, not be decided and dropped "
        "inside renderGraphCanvas"
    )


def test_gc_start_worker_can_start_at_rest_and_freeze_saved_notes():
    source = _text(GRAPH_CANVAS)
    fn = re.search(
        r"(?s)function gcStartWorker\(nodes, edges, world, s = gcTab, viewSeed = null\) \{.*?\n\}\n",
        source,
    )
    assert fn, (
        "gcStartWorker must take a viewSeed ({alpha, freezeIds} or null) "
        "rather than always sending the worker alpha: 1"
    )
    body = gc_worker(source)  # gcStartWorker and the pieces split out of it (L14)
    assert "viewSeed ? viewSeed.alpha : 1" in body or "viewSeed.alpha" in body, (
        "a restored view with nothing left unplaced must be able to start "
        "the worker's simulation at alpha 0, not the unconditional 1 every "
        "other render wants"
    )
    assert re.search(r'type:\s*"freeze".*freezeIds', body, re.S), (
        "the notes a restored view already placed must be frozen (the same "
        "message a drag already uses to hold everything else still) while "
        "an unplaced note's reheat settles, or they would drift along with it"
    )


def test_the_worker_thaws_the_view_s_notes_once_it_settles():
    source = _text(GRAPH_CANVAS)
    assert "_viewRestorePending" in source, (
        "a view-restore reheat must release the notes it froze once the "
        "simulation ends (`thaw`, the same release a drag's freeze gets), "
        "or every restored note stays permanently held"
    )
    # The "end" branch of onmessage is a call to `gcOnWorkerEnd` (L14), which holds the thaw.
    end_branch = re.search(r'(?s)message\.type === "end"\) \{\s*gcOnWorkerEnd\(s\);\s*\}', source)
    assert end_branch and "thaw" in gc_worker(source)[gc_worker(source).index("function gcOnWorkerEnd(") :], (
        "the thaw belongs in the worker's \"end\" message handling: releasing "
        "before the reheat is done would let the saved notes drift while the "
        "new one is still being placed"
    )


def test_a_restore_holds_its_notes_from_the_first_step_and_never_warms():
    # Claim #238: a view re-picks its layout, which clears the fit, so the
    # init warmed (450ms of steps) before the separate `freeze` arrived and
    # every saved note moved (726px with a note added since). The hold rides
    # in the init and a restore neither warms nor plays an intro.
    source = _text(GRAPH_CANVAS)
    body = gc_worker(source)
    assert "held: held.has(n.id)," in body
    assert "warm: reframe && !restoring &&" in body
    assert "intro: !gcStill() && !restoring," in body
    render = re.search(r"(?s)async function renderGraphCanvas\(s = gcTab\) \{.*?\n\}\n", source).group(0)
    assert render.index("const restoring = Boolean(graphPendingViewPositions)") < render.index("graphPendingViewPositions = null")
    assert "restore: restoring," in render
    worker = _text(GRAPH_CANVAS.parent / "graph-worker.js")
    init = worker[worker.index('case "init": {') : worker.index('case "params":')]
    assert "if (!n.held || node.fx != null || node.x === undefined) return;" in init
    assert init.index("node.frozenByDrag = true;") < init.index("simulation = d3")
