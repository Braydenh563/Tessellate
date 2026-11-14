"""L-whiteboard-43: a connector whose end attaches to another connector, edge to edge.

`whiteboard-link-edge.js` is run in node against a small stand-in for the board's connector maths (straight lines
between free points, the point at `t` along a line by interpolation). What is under test is the rule: an end stores
`{ id, t }` beside its last point, resolves to the point at `t` along the other connector as it is drawn now, lets go
and keeps its last point when that connector is deleted, and takes hold again when the delete is undone. The wiring
in whiteboard.js is read, because the resolver, the delete and the undo are the board's own.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

PRELUDE = r"""
const wbFmtState = {};
const sketches = [];
const wbState = { sketches };
const wbParsedLink = (s) => { try { const p = JSON.parse(s.data); return p && String(p.type || '').startsWith('link-') ? p : null; } catch { return null; } };
const wbLinkItem = (kind, id) => sketches.find((s) => s.id === id) || null;
const wbMapCrossLinkLook = () => null;
const wbLinkCaps = () => ({});
const wbLinkShape = () => null;
const wbResolveLinkEndpoints = (parsed) => {
  const p = wbFmtState.linkEdge.pinned(parsed);
  return p.sourcePoint && p.targetPoint ? { source: p.sourcePoint, target: p.targetPoint } : null;
};
const wbLinkPathD = (type, s, t) => `M ${s.x} ${s.y} L ${t.x} ${t.y}`;
const wbLinkMidpoint = (d, t) => {
  const n = d.match(/-?[\d.]+/g).map(Number);
  return { x: n[0] + (n[2] - n[0]) * t, y: n[1] + (n[3] - n[1]) * t };
};
const wbSaveSketchProps = async (sketch, partial) => {
  const parsed = JSON.parse(sketch.data);
  Object.assign(parsed, partial);
  for (const k of Object.keys(parsed)) if (parsed[k] === undefined) delete parsed[k];
  sketch.data = JSON.stringify(parsed);
};
//: The batch save the board uses for several rows (test_board_selection_batches); the row's data is already set.
const wbSaveMany = async (rows) => rows.length;
const d3 = { zoomTransform: () => ({ k: 1 }) };
var document = { getElementById: () => ({}) };
const add = (id, data) => sketches.push({ id, data: JSON.stringify({ type: 'link-straight', ...data }) });
const dataOf = (id) => JSON.parse(sketches.find((s) => s.id === id).data);
const L = () => wbFmtState.linkEdge;
"""


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = PRELUDE + frontend_text("whiteboard-link-edge.js") + f"\n(async () => {{ {body} }})().then((v) => console.log(JSON.stringify(v)));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_an_edge_is_only_read_when_it_is_whole():
    got = _run(
        "return [L().edgeOf({ targetEdge: { id: 3, t: 0.25 } }, 'target'), L().edgeOf({ targetEdge: { id: '3', t: 0.25 } }, 'target'),"
        " L().edgeOf({ targetEdge: { id: 3, t: 'x' } }, 'target'), L().edgeOf({ targetEdge: { id: 3, t: 7 } }, 'target'), L().edgeOf({}, 'source')];"
    )
    assert got == [{"id": 3, "t": 0.25}, None, None, {"id": 3, "t": 1}, None]


def test_an_attached_end_sits_at_t_along_the_other_line_and_follows_it():
    got = _run(
        """
        add(1, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 } });
        add(2, { sourcePoint: { x: 50, y: 80 }, targetPoint: { x: 0, y: 0 }, targetEdge: { id: 1, t: 0.5 } });
        const first = wbResolveLinkEndpoints(wbParsedLink(sketches[1])).target;
        await wbSaveSketchProps(sketches[0], { targetPoint: { x: 200, y: 40 } });
        const moved = wbResolveLinkEndpoints(wbParsedLink(sketches[1])).target;
        return { first, moved, plain: wbResolveLinkEndpoints(wbParsedLink(sketches[0])).target };
        """
    )
    assert got["first"] == {"x": 50, "y": 0}, "t = 0.5 along a line from (0,0) to (100,0)"
    assert got["moved"] == {"x": 100, "y": 20}, "the line was re-ended, so the attached end rerouted"
    assert got["plain"] == {"x": 200, "y": 40}, "an ordinary connector is read as it always was"


def test_a_connector_with_no_edge_is_returned_untouched():
    assert _run("add(1, { sourcePoint: { x: 1, y: 1 }, targetPoint: { x: 2, y: 2 } }); const p = wbParsedLink(sketches[0]); return L().pinned(p) === p;") is True


def test_an_end_that_lost_its_line_keeps_its_last_point():
    got = _run(
        """
        add(1, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 } });
        add(2, { sourcePoint: { x: 50, y: 80 }, targetPoint: { x: 30, y: 0 }, targetEdge: { id: 1, t: 0.3 } });
        const seen = wbResolveLinkEndpoints(wbParsedLink(sketches[1])).target;
        sketches.splice(0, 1);
        const after = wbResolveLinkEndpoints(wbParsedLink(sketches[0])).target;
        return { seen, after };
        """
    )
    assert got["seen"] == {"x": 30, "y": 0} and got["after"] == {"x": 30, "y": 0}


def test_deleting_the_line_floats_the_end_free_and_undo_takes_hold_again():
    got = _run(
        """
        add(1, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 } });
        add(2, { sourcePoint: { x: 50, y: 80 }, targetPoint: { x: 0, y: 0 }, sourceEdge: { id: 1, t: 0.2 }, targetEdge: { id: 1, t: 0.8 } });
        const gone = sketches[0];
        const list = L().beforeDelete(gone);
        sketches.splice(0, 1);
        await L().afterDelete(list);
        const floated = dataOf(2);
        add(9, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 } });
        await L().reattach(list, 9);
        return { list, floated, back: dataOf(2) };
        """
    )
    assert [(i["end"], i["t"], i["x"], i["y"]) for i in got["list"]] == [("source", 0.2, 20, 0), ("target", 0.8, 80, 0)]
    f = got["floated"]
    assert "sourceEdge" not in f and "targetEdge" not in f, "the ends let go"
    assert f["sourcePoint"] == {"x": 20, "y": 0} and f["targetPoint"] == {"x": 80, "y": 0}, "and keep the point they had"
    assert got["back"]["sourceEdge"] == {"id": 9, "t": 0.2} and got["back"]["targetEdge"] == {"id": 9, "t": 0.8}


def test_a_point_on_a_line_finds_it_with_t_and_two_lines_never_hold_each_other():
    got = _run(
        """
        add(1, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 } });
        add(2, { sourcePoint: { x: 50, y: 50 }, targetPoint: { x: 0, y: 0 }, targetEdge: { id: 1, t: 0.5 } });
        const near = L().hitAt(25, 4);
        const far = L().hitAt(25, 60);
        const skipOwn = L().hitAt(25, 4, 1);
        const cyc = L().hitAt(50, 25, 2);
        return { near, far, skipOwn, cyc, hangs: L().hangsOn(wbParsedLink(sketches[1]), 1), hangsBack: L().hangsOn(wbParsedLink(sketches[0]), 2) };
        """
    )
    assert got["near"]["id"] == 1 and abs(got["near"]["t"] - 0.25) < 0.01 and got["near"]["y"] == 0
    assert got["far"] is None
    assert got["skipOwn"] is None or got["skipOwn"]["id"] != 1
    assert got["cyc"] is None or got["cyc"]["id"] != 1, "connector 1 does not hang on 2, so it is allowed; 2 itself never is"
    assert got["hangs"] is True and got["hangsBack"] is False


def test_a_chain_and_a_loop_stay_bounded():
    got = _run(
        """
        add(1, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 }, sourceEdge: { id: 2, t: 0.5 } });
        add(2, { sourcePoint: { x: 0, y: 10 }, targetPoint: { x: 100, y: 10 }, sourceEdge: { id: 1, t: 0.5 } });
        return wbResolveLinkEndpoints(wbParsedLink(sketches[0])) !== null;
        """
    )
    assert got is True, "a loop of two connectors resolves (depth limited) instead of recursing for ever"


def test_follow_redraws_the_ones_that_hang_on_a_moved_line():
    got = _run(
        """
        add(1, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 } });
        add(2, { sourcePoint: { x: 0, y: 5 }, targetPoint: { x: 9, y: 9 }, targetEdge: { id: 1, t: 0.5 } });
        add(3, { sourcePoint: { x: 0, y: 5 }, targetPoint: { x: 9, y: 9 } });
        const calls = [];
        L().follow(1, (id, deps) => calls.push(deps.map((d) => d.sketch.id)));
        L().follow(3, (id, deps) => calls.push('never'));
        return calls;
        """
    )
    assert got == [[2]]


def test_it_is_wired_into_the_board():
    board = frontend_text("whiteboard.js")
    assert "wbFmtState.linkEdge?.pinned(parsed) ?? parsed" in board, "every connector is read through the pin"
    assert "wbFmtState.linkEdge?.follow(sketch.id, wbUpdateLinkedSketches)" in board
    assert "wbFmtState.linkEdge?.beforeDelete(d)" in board and "wbFmtState.linkEdge?.afterDelete(edgeEnds)" in board
    assert "wbFmtState.linkEdge?.reattach(entry.edgeEnds, restored.id)" in board
    assert board.count("wbFmtState.linkEdge?.hitAt(") == 3, "the port drag, the end handle and the Arrow tool"
    assert "/js/whiteboard-link-edge.js" in frontend_text("lazy-entries.js")
    assert "innerHTML" not in frontend_text("whiteboard-link-edge.js")


def test_draw_io_gets_the_resolved_point_as_a_free_end_and_reads_it_back():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    source = frontend_text("whiteboard-interchange.js")
    pure = source[: source.index("//: The rows inside an SVG")]
    body = """
        add(1, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 } });
        add(2, { sourcePoint: { x: 50, y: 80 }, targetPoint: { x: 0, y: 0 }, targetEdge: { id: 1, t: 0.5 } });
        await wbSaveSketchProps(sketches[0], { targetPoint: { x: 200, y: 40 } });
        const made = wbBoardToDrawio({ nodes: [], objects: [], sketches }, { title: 'T', box: () => null });
        return made.xml;
    """
    script = PRELUDE + frontend_text("whiteboard-link-edge.js") + pure + f"\n(async () => {{ {body} }})().then((v) => console.log(JSON.stringify(v)));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    xml = json.loads(out.stdout)
    # The second connector's end was at t = 0.5 along a line now running (0,0) to (200,40): (100, 20).
    assert 'as="targetPoint"' in xml and '<mxPoint x="100" y="20" as="targetPoint"/>' in xml, xml
    assert "targetEdge" not in xml and "sourceEdge" not in xml


def test_a_selection_keeps_connectors_on_kept_connectors_and_places_them_after_them():
    got = _run(
        """
        const row = (id, data) => ({ kind: 'sketch', id, link: true, payload: { data: JSON.stringify({ type: 'link-straight', ...data }) } });
        const shape = { kind: 'sketch', id: 5, link: false, payload: {} };
        const rows = [
          shape,
          row(1, { sourceKind: 'sketch', sourceId: 5, targetPoint: { x: 100, y: 0 } }),
          row(2, { sourcePoint: { x: 1, y: 1 }, targetPoint: { x: 2, y: 2 }, targetEdge: { id: 1, t: 0.5 } }),
          row(3, { sourcePoint: { x: 1, y: 1 }, targetPoint: { x: 2, y: 2 }, targetEdge: { id: 99, t: 0.5 } }),
          row(4, { sourcePoint: { x: 1, y: 1 }, targetPoint: { x: 2, y: 2 } }),
        ];
        const kept = L().keptRows(rows).map((r) => r.id);
        const remap = new Map([['sketch:5', 50], ['sketch:1', 10]]);
        const placed = L().place(JSON.parse(rows[2].payload.data), remap, 10, 20);
        const early = L().place(JSON.parse(rows[2].payload.data), new Map([['sketch:5', 50]]), 10, 20);
        return { kept, placed, early };
        """
    )
    assert got["kept"] == [5, 1, 2], "a connector on a missing connector, and a loose one, are left out"
    assert got["placed"]["targetEdge"] == {"id": 10, "t": 0.5}
    assert got["placed"]["targetPoint"] == {"x": 12, "y": 22} and got["placed"]["sourcePoint"] == {"x": 11, "y": 21}
    assert got["early"] is None, "waits for the connector it hangs on"


def test_the_interchange_goes_through_the_edge_rules():
    source = frontend_text("whiteboard-interchange.js")
    assert "wbFmtState.linkEdge.keptRows(rows)" in source and "wbFmtState.linkEdge.place(" in source
    assert "?.pinned(stored)" in source, "the draw.io writer reads each connector through the pin"


def test_dragging_an_end_over_a_connector_lights_it_and_letting_go_takes_the_cue_away():
    got = _run(
        """
        const made = new Map();
        const el = (tag) => ({ tag, attrs: {}, kids: [], setAttribute(k, v) { this.attrs[k] = v; }, append(...n) { this.kids.push(...n); }, appendChild(n) { this.kids.push(n); },
          get firstElementChild() { return this.kids[0]; }, get lastElementChild() { return this.kids[this.kids.length - 1]; }, remove() { made.delete(this.attrs.id); } });
        const zoom = el('g');
        document = { getElementById: (id) => (id === 'wb-overlay-zoom-group' ? zoom : made.get(id) || null), createElementNS: (ns, tag) => {
          const n = el(tag); const set = n.setAttribute.bind(n); n.setAttribute = (k, v) => { set(k, v); if (k === 'id') made.set(v, n); }; return n; } };
        add(1, { sourcePoint: { x: 0, y: 0 }, targetPoint: { x: 100, y: 0 } });
        const over = L().cue([25, 4]);
        const layer = made.get('wb-edge-cue');
        const lit = layer && { d: layer.kids[0].attrs.d, cx: layer.kids[1].attrs.cx, stroke: layer.kids[0].attrs.stroke };
        const own = L().cue([25, 4], 1);
        const gone = !made.get('wb-edge-cue');
        L().cue([25, 4]);
        L().cue(null);
        return { over: over && over.id, lit, own, gone, after: !made.get('wb-edge-cue') };
        """
    )
    assert got["over"] == 1 and got["lit"]["d"] == "M 0 0 L 100 0" and got["lit"]["cx"] == "25" and got["lit"]["stroke"] == "var(--accent)"
    assert got["own"] is None and got["gone"] is True, "the connector being re-ended is never lit"
    assert got["after"] is True, "letting go takes the cue away"


def test_the_cue_is_wired_into_both_end_drags():
    board = frontend_text("whiteboard.js")
    assert board.count("wbFmtState.linkEdge?.cue(") == 4, "the port drag and the end handle, each lit on the way and cleared at the end"
