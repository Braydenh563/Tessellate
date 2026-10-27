"""The graph moves again, fits its screen, and a small map has room (INBOX 775).

The owner, 2026-10-10, 34 notes: "it didnt zoom in or fit to my screen?? I
pressed the fit button and it didnt do much", the bubbles crowding, and "I
prefered the force and movement how the graph used to be, theres no movement
to it now :(" / "when the graph readjusts it just appears there :(".

Measured with scratchpad/ui-sweeps/graphfeel.js (34 notes, 1440x900): after
the reveal a node travelled 26 px on screen (the warm-up of INBOX 738 ran out
of sight); with the playback, 280 to 440 px over about a second. Round 2 (the
owner: "look at how the movement is in main"): origin/main's live settle
showed 141 px of layout travel from alpha 0.45, at the zoom clamp (k 2.5)
before its fit pulled back; the playback now runs one tick a frame from alpha
1 (431 px, 0.9 s to 2.5 s) with the camera already set (k 1.22 to 1.33). The fit's
frame is tested in test_graph_fit_balance.py; the layout here runs the shipped
worker under tests/_graph_worker_harness.js.
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
WORKER = (JS / "graph-worker.js").read_text(encoding="utf-8")
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _scenario(n: int = 15, **extra) -> dict:
    nodes = [{"id": i, "group": f"g{i % 3}", "r": 7} for i in range(n)]
    edges = [{"source": i, "target": (i // 5) * 5, "kind": "link"} for i in range(n) if i % 5]
    return {"nodes": nodes, "edges": edges, "ticks": 900, **extra}


def _run(scenario: dict) -> dict:
    out = subprocess.run(
        ["node", str(HARNESS)], input=json.dumps(scenario), capture_output=True, text=True, check=True, timeout=60
    ).stdout
    return json.loads(out)


@needs_node
def test_a_warmed_layout_is_played_back_as_a_short_flow_after_its_frame():
    """The intent moved on 2026-10-27: the owner saw the playback from full heat
    as "very very not plesant to look at all the adjusting" and asked for it
    "smooth and flowy". The opening is now settled and untangled out of sight
    and played as one short flow into that map (`introInto`): a hidden map
    blooms in from a slight contraction at a low heat (`BLOOM_ALPHA`), one on
    screen flows on from where it stands (`RESTART_ALPHA`). There is still
    motion (owner, 2026-10-10: "theres no movement to it now"), held through the
    canvas's fade first: INTRO_HOLD + the recorded frames."""
    bloom = _run(_scenario(warm=True, intro=True, bloom=True))
    assert bloom["framed"]
    assert 8 + 30 <= bloom["introTicks"] <= 8 + 61, bloom["introTicks"]
    assert abs(bloom["firstIntroAlpha"] - 0.1) < 0.01, bloom["firstIntroAlpha"]
    shown = _run(_scenario(warm=True, intro=True))
    assert shown["framed"]
    assert 8 + 45 <= shown["introTicks"] <= 8 + 91, shown["introTicks"]
    assert abs(shown["firstIntroAlpha"] - 0.3) < 0.01, shown["firstIntroAlpha"]


@needs_node
def test_the_playback_ends_where_the_layout_would_have_without_it():
    played = _run(_scenario(warm=True, intro=True))["positions"]
    plain = _run(_scenario(warm=True))["positions"]
    for key, (x, y) in plain.items():
        assert abs(played[key][0] - x) < 0.01 and abs(played[key][1] - y) < 0.01, key


@needs_node
def test_without_intro_nothing_is_played_back():
    # A reader who asked for less motion: the main thread does not ask.
    got = _run(_scenario(warm=True))
    assert not got["framed"] and got["introTicks"] == 0


def test_less_motion_does_not_ask_for_the_playback():
    # Brief 100: `gcStill` asks the system and the app's own Reduce motion.
    assert "intro: !gcStill() && !restoring," in CANVAS, "a saved view restored plays no intro (claim #238)"
    still = CANVAS[CANVAS.index("\nfunction gcStill(") : CANVAS.index("\n}\n", CANVAS.index("\nfunction gcStill("))]
    assert "prefers-reduced-motion: reduce" in still and 'dataset?.motion === "reduced"' in still


def test_the_frame_is_fitted_before_the_playback_and_the_fits_wait_for_it():
    body = CANVAS[CANVAS.index("\nfunction gcFrameIntro(") : CANVAS.index("\n}\n", CANVAS.index("\nfunction gcFrameIntro("))]
    assert 'fitGraphToView(s.svg, null, s.zoom, target, s.dims.w, s.dims.h, s.canvas?.style.opacity === "0");' in body
    assert "gcReveal(s);" in body
    assert "if (!gcAutoFitDone(s) && s.nodes.length && !s.intro) {" in CANVAS
    # Balancing on dots still on their way would undo the frame.
    assert "|| s.intro) return;" in CANVAS


def test_a_drag_stops_the_playback():
    assert 'const INTRO_KEEPS = new Set(["recycle", "init"]);' in WORKER
    # 2026-10-27: the same message also stops the settle glide and the settle out
    # of sight, so the cancel became a block; the playback is still stopped first.
    assert "if (!INTRO_KEEPS.has(message.type)) {\n    introCancel();\n    settleGlideCancel();\n    pendingCancel();" in WORKER


def _small_spread(n: int) -> float:
    script = "\n".join(
        [
            re.search(r"\nconst DENSITY_REFERENCE = [^;]+;", WORKER).group(0),
            re.search(r"\nconst SMALL_SPREAD = [^;]+;", WORKER).group(0),
            re.search(r"\nconst SMALL_FROM = [^;]+;", WORKER).group(0),
            WORKER[WORKER.index("\nfunction smallSpread(") : WORKER.index("\n}\n", WORKER.index("\nfunction smallSpread(")) + 3],
            f"console.log(smallSpread({n}));",
        ]
    )
    return float(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
@pytest.mark.parametrize(("n", "expected"), [(1, 2.4), (3, 2.4), (34, 1.227), (40, 1.0), (300, 1.0)])
def test_a_small_map_spreads_and_a_big_one_is_unchanged(n, expected):
    assert abs(_small_spread(n) - expected) < 0.01


@needs_node
def test_three_notes_stand_apart_and_never_overlap():
    nodes = [{"id": i, "group": "g", "r": 8.5} for i in range(3)]
    edges = [{"source": 0, "target": 1, "kind": "link"}, {"source": 1, "target": 2, "kind": "link"}]
    pos = _run({"nodes": nodes, "edges": edges, "ticks": 600})["positions"]
    pts = list(pos.values())
    gaps = [((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for i, a in enumerate(pts) for b in pts[i + 1 :]]
    # The base link length at three notes was 62; spread, a link is over 120.
    assert min(gaps) > 120, gaps


GRAPH = (JS / "graph.js").read_text(encoding="utf-8")


def test_an_open_panel_is_kept_clear_and_a_fitted_map_refits_round_it():
    # INBOX 792, the owner: fitting "should be based on what panels are
    # currently showing". Measured (scratchpad/ui-sweeps/graphfeel.js's panel
    # probe): Options open, the dots' right edge 998 against the panel's 1079.
    overlays = CANVAS[CANVAS.index("const GC_FIT_OVERLAYS = [") : CANVAS.index("];", CANVAS.index("const GC_FIT_OVERLAYS = ["))]
    for panel in ("#graph-options", "#graph-help-panel", "#graph-selection-dock", "#graph-trace", "#graph-topic"):
        assert f'"{panel}"' in overlays, panel
    assert 'for (const el of document.querySelectorAll(GC_FIT_OVERLAYS.join(","))) s.observer.observe(el);' in CANVAS
    # The owner, 2026-10-11: opening or closing the gear panel or the dock's
    # menu must not move a node or the camera, so those two never refit
    # (graphmenustill.js measures it), and so must the help panel (2026-10-12:
        # it moved the camera 215px); the other panels still do.
    assert "if (entries.some((entry) => entry.target.id !== s.boxId && !entry.target.matches(GC_FIT_MENUS))) gcRefitForPanels(s);" in CANVAS
    assert 'const GC_FIT_MENUS = "#graph-options, #graph-help-panel, #graph-card > .graph-overlay > .dock";' in CANVAS
    refit = CANVAS[CANVAS.index("\nfunction gcRefitForPanels(") : CANVAS.index("\n}\n", CANVAS.index("\nfunction gcRefitForPanels("))]
    assert "s.userZoomed || s.intro || !s.zoom" in refit and "else if (s.fittedOnce) fitGraphToView(" in refit


def test_the_zoom_buttons_count_as_moving_the_camera_and_fit_as_fitting_it():
    zoom = GRAPH[GRAPH.index("\nfunction graphZoomBy(") : GRAPH.index("\n}\n", GRAPH.index("\nfunction graphZoomBy("))]
    assert "gcTab.userZoomed = true;" in zoom
    assert "if (tab) gcTab.userZoomed = nodes.length !== gcTab.nodes.length;" in GRAPH


def test_a_map_already_showing_is_never_hidden_to_relayout():
    # Round 2: "I just change views or reset it and it just suddenly changes
    # or disappears and reappears". Only a canvas that has shown nothing hides.
    assert "if (reframe && s.canvas && !s.shown) {" in CANVAS
    assert "warm: reframe && !restoring && !(viewSeed && viewSeed.alpha === 0)," in CANVAS
    reveal = CANVAS[CANVAS.index("\nfunction gcReveal(") : CANVAS.index("\n}\n", CANVAS.index("\nfunction gcReveal("))]
    assert "s.shown = true;" in reveal
    intro = CANVAS[CANVAS.index("\nfunction gcFrameIntro(") : CANVAS.index("\n}\n", CANVAS.index("\nfunction gcFrameIntro("))]
    assert 's.canvas?.style.opacity === "0");' in intro


TWEEN = "\n".join(
    [
        re.search(r"\nconst GC_LAYOUT_MS = [^;]+;", CANVAS).group(0),
        re.search(r"\nconst GC_BORN_MS = [^;]+;", CANVAS).group(0),
        CANVAS[CANVAS.index("\nfunction gcTweenFromPrior(") : CANVAS.index("\n}\n", CANVAS.index("\nfunction gcTweenFromPrior(")) + 3],
        CANVAS[CANVAS.index("\nfunction gcBornAlpha(") : CANVAS.index("\n}\n", CANVAS.index("\nfunction gcBornAlpha(")) + 3],
        CANVAS[CANVAS.index("\nfunction gcStill(") : CANVAS.index("\n}\n", CANVAS.index("\nfunction gcStill(")) + 3],
        GRAPH[GRAPH.index("\nfunction graphGlideMs(") : GRAPH.index("\n}\n", GRAPH.index("\nfunction graphGlideMs(")) + 3],
        """
let still = false;
const window = { matchMedia: () => ({ matches: still }) };
const document = { documentElement: { dataset: {} } };
const performance = { now: () => 1000 };
const run = (move) => {
  const s = {};
  const nodes = [{ id: 1, x: 100, y: 0 }, { id: 2, x: 50, y: 50 }];
  gcTweenFromPrior(s, nodes, new Map([[1, { x: 0, y: 0 }]]), move);
  return { s, nodes, born: [gcBornAlpha(nodes[1], 1000), gcBornAlpha(nodes[1], 1160), gcBornAlpha(nodes[1], 2000)] };
};
const moved = run(true), kept = run(false);
still = true;
const calm = run(true);
console.log(JSON.stringify({ moved, kept, calm }));
""",
    ]
)


@needs_node
def test_a_computed_layout_glides_from_where_the_notes_were_and_new_ones_fade_in():
    got = json.loads(subprocess.run(["node", "-e", TWEEN], capture_output=True, text=True, check=True).stdout)
    m = got["moved"]
    assert m["nodes"][0]["x"] == 0 and m["nodes"][0]["_toX"] == 100 and m["s"]["gliding"] and m["s"]["glideMs"] == 700
    assert m["born"][0] == 0 and 0.4 < m["born"][1] < 0.6 and m["born"][2] == 1
    # The force layout's worker carries the notes: only the new one is marked.
    k = got["kept"]
    assert k["nodes"][0]["x"] == 100 and not k["s"].get("gliding") and k["born"][0] == 0
    # Less motion keeps the cut.
    c = got["calm"]
    assert c["nodes"][0]["x"] == 100 and c["born"][0] == 1


def test_topic_hulls_belong_to_the_force_layout_and_a_tree_fits_at_0_4():
    assert '|| s.tree || graphColourMode() !== "topic"' in CANVAS
    assert "const fit = radial || arc || whole || both >= 0.4 ? both : (width - 20) / spanX;" in GRAPH
    assert "gcTweenFromPrior(s, nodes, prior);" in CANVAS


# A small pull on a node heats a small part of the map (INBOX 839).


def test_a_small_pull_on_a_graph_node_heats_a_small_part_of_the_map():
    """"small adjustments and graph nodes being pulled in slightly are glitchy
    and jittery, not smooth" (INBOX 839). The worker raised the drag target to
    0.3 the moment a node was pressed. Measured per worker tick on 34 notes, an
    8px pull, two runs each: ticks above 1px 38 and 15, the last at tick 41 and
    179, one run with a 28px step and 8 re-accelerations before; 5 and 3, the
    last at tick 7 and 3, largest step 2.7px and 1 re-acceleration after. A
    120px pull is unchanged (90 against 92 to 96 ticks above 1px, 12.3 against
    12.6px). The target follows the distance carried from the press, easing from
    `DRAG_ALPHA_MIN` to `DRAG_ALPHA`."""
    worker = (JS / "graph-worker.js").read_text(encoding="utf-8")
    assert "const DRAG_ALPHA_MIN = 0.04;" in worker and "const DRAG_FULL_DISTANCE = 90;" in worker
    assert "simulation.alphaTarget(DRAG_ALPHA).alpha(Math.max(simulation.alpha(), DRAG_ALPHA));" not in worker
    start = worker[worker.index('if (message.phase === "start") {') :]
    assert "dragOrigin = { x: node.x, y: node.y };" in start.split('} else if (message.phase === "move")')[0]
    move = start.split('} else if (message.phase === "move") {')[1].split("} else {")[0]
    assert "dragHeat(message.x, message.y)" in move
    assert "dragOrigin = null;" in start
