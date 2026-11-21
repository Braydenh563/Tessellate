"""Brief 100, the graph's feel (INBOX 802, 864, 865, and the owner
2026-10-11: "there is still no smooth transition loading up the app nd
viewing the graph, it kinda just appears after the page loads").

Measured with `scratchpad/ui-sweeps/graph100.js` (200 and 2,000 notes); these
tests hold the pure pieces by running them in node, and read the source for
the wiring a canvas hides from the lints."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import gc_frame, unwrapped

ROOT = Path(__file__).resolve().parent.parent
CANVAS = unwrapped((ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    found = re.search(rf"^(?:async )?function {name}\(.*?^\}}", CANVAS, re.S | re.M)
    assert found, name
    return found.group(0)


def _const(name: str) -> str:
    found = re.search(rf"^const {name} = .*?;$", CANVAS, re.M)
    assert found, name
    return found.group(0)


def _node(script: str) -> dict:
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout
    return json.loads(out)


@needs_node
def test_the_settled_map_is_kept_and_a_fresh_page_starts_from_it():
    script = "\n".join(
        [
            _const("GC_POS_KEY"),
            _const("GC_POS_MAX"),
            _fn("gcPositionsSig"),
            _fn("gcSavePositions"),
            _fn("gcCachedPositions"),
            """
let graphFocusModeId = null;
let shape = "organic";
const gcWorkerParams = () => ({ shape });
const store = new Map();
let blocked = false;
const localStorage = {
  getItem(k) { if (blocked) throw new Error("blocked"); return store.has(k) ? store.get(k) : null; },
  setItem(k, v) { if (blocked) throw new Error("blocked"); store.set(k, v); },
};
// prefs.js's promise, kept: a blocked storage reads as the fallback and a
// refused write answers false, neither throws.
const prefs = {
  json(k, fallback) { try { const raw = localStorage.getItem(k); return raw ? JSON.parse(raw) ?? fallback : fallback; } catch { return fallback; } },
  set(k, v) { try { localStorage.setItem(k, String(v)); return true; } catch { return false; } },
  remove(k) { try { store.delete(k); } catch {} },
};
const s = { size: "full", tree: null, layoutSeed: 0, nodes: [{ id: 7, x: 10.4, y: -3.6 }, { id: 9, x: NaN, y: 1 }] };
gcSavePositions(s);
const back = gcCachedPositions(s);
shape = "clusters";
const otherShape = gcCachedPositions(s);
shape = "organic";
const pane = gcCachedPositions({ ...s, size: "pane" });
graphFocusModeId = 7;
const focused = gcCachedPositions(s);
graphFocusModeId = null;
blocked = true;
let threw = false;
try { gcSavePositions(s); gcCachedPositions(s); } catch (e) { threw = true; }
console.log(JSON.stringify({ back, otherShape, pane, focused, threw, blockedRead: gcCachedPositions(s) }));
""",
        ]
    )
    out = _node(script)
    assert out["back"] == {"7": {"x": 10, "y": -4}}, "a settled note is kept, a note with no place is not"
    assert out["otherShape"] is None, "positions settled under other forces are not reused"
    assert out["pane"] is None and out["focused"] is None, "only the tab's whole map is kept"
    assert out["threw"] is False and out["blockedRead"] is None, "a blocked store costs the head start, nothing else"


def test_the_cache_is_read_on_a_first_draw_and_written_at_rest():
    render = _fn("renderGraphCanvas")
    assert (
        'graphPendingViewPositions || back || (s.layoutKind === "force" && !prior.size ? gcCachedPositions(s) : null);'
        in render
    ), "a page's first force draw starts from the kept positions, through the saved-view path"
    # L14: the "end" branch hands over to `gcOnWorkerEnd`, which keeps them.
    assert '} else if (message.type === "end") {\n        gcOnWorkerEnd(s);' in CANVAS
    end = CANVAS[CANVAS.index("function gcOnWorkerEnd(") :]
    assert "gcSavePositions(s);" in end[: end.index("\n  }\n")], "the positions are kept when the layout comes to rest"


def test_the_map_arrives_over_a_fade_the_reader_can_see():
    reveal = _fn("gcReveal")
    assert 'opacity calc(var(--ui-slow) * 2) var(--ease-out)' in reveal


@needs_node
def test_the_hover_eases_over_the_motion_tokens_and_cuts_with_less_motion():
    script = "\n".join(
        [
            _const("GC_FADE_MS"),
            _fn("gcMs"),
            _fn("gcStill"),
            _fn("gcFadeStep"),
            """
let reduce = false, appMotion = "full";
const reducedMotionWanted = () => reduce || appMotion === "reduced";
const document = { documentElement: { dataset: { get motion() { return appMotion; } } } };
let gcTokens = { fadeMs: gcMs("0.2s") };
let t = 1000;
const performance = { now: () => t };
const s = {};
gcFadeStep(s, false);
t += 16.7;
const step = gcFadeStep(s, gcStill());
appMotion = "reduced";
const appStill = gcStill();
appMotion = "full"; reduce = true;
const osStill = gcStill();
reduce = false;
gcTokens = { fadeMs: gcMs("0s") };
t += 16.7;
const off = gcFadeStep(s, gcStill());
console.log(JSON.stringify({ ms: [gcMs("0.2s"), gcMs("120ms"), gcMs("0s"), gcMs("")], step, appStill, osStill, off }));
""",
        ]
    )
    out = _node(script)
    assert out["ms"] == [200, 120, 0, 0]
    assert abs(out["step"] - 16.7 / 200) < 1e-9, "a frame moves a 200 ms fade by its share"
    assert out["appStill"] is True and out["osStill"] is True, "either cause of reduced motion counts"
    assert out["off"] == 1, "interface animations off (a 0s token) lands the fade at once"


@needs_node
def test_a_new_note_starts_beside_its_neighbours_not_on_the_centre_spiral():
    script = "\n".join(
        [
            _fn("gcSeedBesideNeighbours"),
            """
const nodes = [
  { id: 1, x: 100, y: 100, category: "A" },
  { id: 2, x: 300, y: 100, category: "A" },
  { id: 3, category: "A" },
  { id: 4, category: "A" },
  { id: 5, category: "B" },
];
const s = { adj: new Map([[1, new Set([3])], [2, new Set([3])], [3, new Set([1, 2])], [4, new Set()], [5, new Set()]]),
  byId: new Map(nodes.map((n) => [n.id, n])) };
gcSeedBesideNeighbours(s, nodes);
console.log(JSON.stringify(nodes.map((n) => [n.x ?? null, n.y ?? null])));
""",
        ]
    )
    out = _node(script)
    assert abs(out[2][0] - 200) <= 12.5 and abs(out[2][1] - 100) <= 12.5, "beside the middle of its linked notes"
    assert abs(out[3][0] - 200) <= 12.5 and abs(out[3][1] - 100) <= 12.5, "unlinked: beside its category"
    assert out[4] == [None, None], "nothing placed to stand beside: left for the spiral"


def test_an_update_reheats_like_a_drag_and_leaving_notes_keep_their_look():
    start = _fn("gcStartWorker")
    assert _const("GC_UPDATE_ALPHA") == "const GC_UPDATE_ALPHA = 0.3;"
    assert "if (init.alpha === 1 && viewSeed?.holdIfSettled && s.lastForces === forces) init.alpha = GC_UPDATE_ALPHA;" in start
    mark = _fn("gcMarkLeaving")
    assert "sprite: n._sprite || null," in mark and "lines.lineTo(b.x, b.y);" in mark
    assert _const("GC_LEAVING_MAX") == "const GC_LEAVING_MAX = 2500;", "a category of hundreds fades too"
    draw = gc_frame(CANVAS)
    assert draw.index("gcDrawLeavingLines(ctx, s, performance.now());") < draw.index("gcDrawLeaving(ctx, s, bornAt);")


def test_a_frame_of_a_hover_fade_builds_no_style_objects_or_keys():
    draw = gc_frame(CANVAS)
    assert "{ ...style" not in draw, "an edge's look is worked out once per render (gcEdgeLook)"
    assert "edge._keys[slot] ||" in draw
    assert "gcBowPoint(a, b, gcBowScratch, edge._side)" in draw
    assert "node._spritePx !== px" in draw


#: The bloom block exactly as it stood before Brief 100: the owner said "keep
#: the glow the same", so its text is pinned (the pixel check, glow.js against
#: the base sprite, measured a 0 difference on the glow ring).
GLOW = """  if (gcHexToRgb(colour)) {
    const bloom = c.createRadialGradient(half, half, r * 0.9, half, half, half);
    const rgb = gcHexToRgb(colour).join(", ");
    bloom.addColorStop(0, `rgba(${rgb}, ${hub ? 0.15 : 0.09})`);
    bloom.addColorStop(1, `rgba(${rgb}, 0)`);"""


@needs_node
def test_the_node_gets_a_shaded_core_and_a_rim_and_the_glow_is_unchanged():
    sprite = _fn("gcNodeSprite")
    assert GLOW in sprite
    assert "const glow = hub ? Math.round(r * 0.8) + 3 : Math.round(r * 0.45) + 2;" in sprite
    assert sprite.index(GLOW) < sprite.index("gcPaintCore(c, half, r, colour);")
    core = _fn("gcPaintCore")
    assert "createRadialGradient" in core and "c.stroke()" in core
    out = _node(
        _fn("gcHexToRgb")
        + _fn("gcMixRgb")
        + """
        console.log(JSON.stringify([gcMixRgb([100, 200, 0], 255, 0.08), gcMixRgb([100, 200, 0], 0, 0.25)]));
        """
    )
    assert out == ["rgb(112, 204, 20)", "rgb(75, 150, 0)"]


def test_the_note_whose_card_is_open_wears_the_focus_ring():
    draw = gc_frame(CANVAS)
    assert 'const openId = s.size === "full" && typeof graphPopupId !== "undefined" ? graphPopupId : null;' in draw
    assert "node.id === gcKeyboardId(s) || node.id === openId" in draw
    graph = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
    for fn in ("openGraphPopup", "closeGraphPopup"):
        body = re.search(rf"(?:async )?function {fn}\(.*?\n}}\n", graph, re.S).group(0)
        assert "gcRequestDraw(gcTab)" in body


GRAPH_JS = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")


def test_a_fit_centres_on_the_canvas_not_round_the_corner_widgets():
    # INBOX 802: "why's the graph so positioned to the right and not in the
    # middle??" Measured (scratchpad/g100 fitc.js): the minimap's corner box
    # reserved a 190px left column, margins 418 against 286; now 352 and 352.
    overlays = _const_block("GC_FIT_OVERLAYS")
    assert '"#graph-minimap"' not in overlays and '"#graph-zoom"' not in overlays
    assert '"#graph-options"' in overlays


def _const_block(name: str) -> str:
    start = CANVAS.index(f"const {name} = [")
    return CANVAS[start : CANVAS.index("];", start)]


@needs_node
def test_every_camera_move_glides_on_the_token_and_cuts_with_less_motion():
    # Every camera move is one `graphGlide(...)` call (L10: it also hands an interrupted glide's speed
    # on), and that takes its length from `graphGlideMs`; no call builds its own transition.
    moves = re.findall(r"graphGlide\((?:s\.)?(?:svg|graphSvg)[^;]*", GRAPH_JS + CANVAS)
    assert len(moves) >= 9, moves
    assert ".transition().duration(" not in re.sub(r"function graphGlide\(.*?^\}", "", GRAPH_JS, flags=re.S | re.M) + CANVAS
    assert "const ms = graphGlideMs(base);" in GRAPH_JS
    assert 'if (animate) graphGlide(graphSvg, graphZoom, "transform", [target], 250);' in GRAPH_JS
    glide = re.search(r"^function graphGlideMs\(.*?^\}", GRAPH_JS, re.S | re.M).group(0)
    out = _node(
        glide
        + """
        let still = false; const gcStill = () => still; let gcTokens = {};
        const a = graphGlideMs(500);
        gcTokens = { hoverMs: 100 }; const b = graphGlideMs(500);
        gcTokens = { hoverMs: 0 }; const c = graphGlideMs(500);
        gcTokens = { hoverMs: 200 }; still = true; const d = graphGlideMs(500);
        console.log(JSON.stringify([a, b, c, d]));
        """
    )
    assert out == [500, 250, 0, 0]
    assert "s.glideMs = Math.max(1, graphGlideMs(GC_LAYOUT_MS));" in CANVAS


DROP = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const timers = [], sent = [];
const sandbox = { console, Math, Date, Float32Array, Map, Set,
  setTimeout: (fn) => { timers.push(fn); return timers.length; }, clearTimeout: () => {},
  setInterval: () => 0, clearInterval: () => {}, performance: { now: () => Date.now() },
  postMessage: (m) => sent.push(m) };
sandbox.self = sandbox;
vm.createContext(sandbox);
sandbox.importScripts = (url) => { const f = path.join(root, url.replace(/^\//, "")); vm.runInContext(fs.readFileSync(f, "utf8"), sandbox); };
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sandbox);
const n = 15;
const nodes = Array.from({ length: n }, (_, i) => ({ id: i, r: 7, group: "g" + (i % 3) }));
const edges = Array.from({ length: n }, (_, i) => i).filter((i) => i % 5).map((i) => ({ source: i, target: Math.floor(i / 5) * 5, kind: "link" }));
const send = (data) => sandbox.onmessage({ data });
// As the main thread does: read the last posted positions, hand each buffer back.
let last = null, ended = false;
const drain = () => {
  for (const m of sent) {
    if (m.type === "tick") last = Array.from(m.positions);
    if (m.type === "end") ended = true;
  }
  sent.length = 0;
  sandbox.onmessage({ data: { type: "recycle", buffer: new Float32Array(n * 2).buffer } });
};
const spin = (most) => { for (let i = 0; i < most && timers.length; i++) { timers.shift()(); drain(); } drain(); };
const at = (id) => [last[id * 2], last[id * 2 + 1]];
send({ type: "init", epoch: 1, nodes, edges, params: { gravity: 50, spread: 50, lengthByScore: true, groupBy: true, orbit: true }, world: { left: -900, top: -900, right: 900, bottom: 900, aspect: 0.5 }, alpha: 1 });
spin(2000);
const from = at(3);
const drop = [from[0] + 300, from[1] - 200];
send({ type: "drag", phase: "start", id: 3, x: from[0], y: from[1] });
send({ type: "drag", phase: "move", id: 3, x: drop[0], y: drop[1] });
spin(20);
send({ type: "drag", phase: "end", id: 3, keep: false });
ended = false;
spin(40);
const mid = at(3);
const midEnded = ended;
spin(6000);
const end = at(3);
// After rest the note is free again: a pin it never asked for is not left on it.
send({ type: "reheat", alpha: 0.5 });
spin(30);
const freed = at(3);
console.log(JSON.stringify({ from, drop, mid, midEnded, end, ended, freed }));
"""


@needs_node
def test_a_dropped_note_settles_near_where_it_was_put_and_is_never_pinned():
    # INBOX 802: measured in the app (scratchpad/g100 drag.js), a note dropped
    # 286px away came 268px back within a second. Held until rest, it then
    # never moved again (the owner, 2026-10-11: "moving nodes keeps them
    # stuck there"). Now let go on release at a low heat: it eases into place
    # near the drop (a 360-unit drop: 43 at 40 ticks, 58 at rest; 86 at the
    # 0.05 tried first) and is free (it moves under a reheat).
    out = _node_args(DROP, str(ROOT / "frontend"))
    dist = lambda a, b: ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5  # noqa: E731
    assert not out["midEnded"] and 0.5 < dist(out["mid"], out["drop"]) < 60, out
    assert out["ended"] and dist(out["end"], out["drop"]) < 60, out
    assert dist(out["freed"], out["end"]) > 0.5, out
    worker = (ROOT / "frontend" / "js" / "graph-worker.js").read_text(encoding="utf-8")
    release = worker[worker.index("if (!message.keep) {\n          node.fx = null;") :][:200]
    # The release heat is the drag's reach's share of it since INBOX 1531
    # (`nudgeHeat`, the whole of it from `DRAG_FULL_DISTANCE`, as this drop is).
    assert "simulation.alpha(Math.min(Math.max(simulation.alpha(), RELEASE_ALPHA_MIN), RELEASE_ALPHA) * nudgeHeat())" in release


def _node_args(script: str, *args: str) -> dict:
    out = subprocess.run(["node", "-e", script, *args], capture_output=True, text=True, check=True, timeout=60).stdout
    return json.loads(out)


CSS_GRAPH = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
CSS_LAZY = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")


def test_the_constellation_keeps_its_room_and_fades_in_once():
    # Measured on a reload (scratchpad/g100 load.js ART=1): the holder sat at
    # 0px for 2.8s, then took 220px and full opacity in one frame. Now 220px
    # from the first frame and a fade with no pop.
    assert ".art-holder {\n  min-block-size: 220px;\n}" in CSS_GRAPH
    assert "const height = 220;" in (ROOT / "frontend" / "js" / "dash-art.js").read_text(encoding="utf-8")
    assert ".art-holder:empty {" in CSS_GRAPH
    start = CSS_GRAPH.index("@starting-style {\n  .art-holder > canvas:not(.art-veil) {\n    opacity: 0;")
    #: A theme change's sky, mounted after the veil that fades over it, starts opaque.
    assert ".art-holder > .art-veil ~ canvas {\n    opacity: 1;" in CSS_GRAPH[start : start + 200]
    tail = CSS_GRAPH[start : start + 900]
    assert ':root[data-motion="reduced"] .art-holder > canvas:not(.art-veil) {\n  transition: none;' in tail


def test_the_first_map_waits_on_a_soft_placeholder_and_cuts_with_less_motion():
    render = _fn("renderGraphCanvas")
    assert render.index("if (!s.shown) gcArriving(s, true);") < render.index("await apiJson(endpoint)")
    failed = render[render.index("  if (!data) {") :]
    assert failed.index("gcArriving(s, false);") < failed.index("surfaceFailed(")
    assert "if (!data.nodes.length) gcArriving(s, false);" in render
    reveal = _fn("gcReveal")
    assert "gcArriving(s, false);" in reveal
    assert 'gcStill() ? "none" : "opacity calc(var(--ui-slow) * 2) var(--ease-out)"' in reveal
    arriving = _fn("gcArriving")
    assert 'box.classList.remove("graph-arriving"), 6000' in arriving
    assert "#graph-box.graph-arriving::after {\n  opacity: 1;" in CSS_LAZY
    assert "@keyframes graph-arriving" in CSS_LAZY
    assert ':root[data-motion="reduced"] #graph-box::after {\n  transition: none;\n  animation: none;' in CSS_LAZY
