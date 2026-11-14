"""Board state per instance (L-whiteboard-53, for L-documents-104: a board edited
in place inside a document, one instance per embed).

`whiteboard-instances.js` keeps one object per mounted board and swaps the
board's live globals (`wbState`, `currentBoardId`, `wbSelectedItem`,
`wbMultiSelection`, `wbUndoStack`, `wbRedoStack`, `wbZoom`) in and out on
`wbInstances.activate`, so the nine hundred call sites that read them keep
meaning "the active board" and the full-page board is the default instance.
The file is run in node against stubs here, the way test_map_add_speed.py runs
`wbMapCache.renderAdd`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
SRC = (JS / "whiteboard-instances.js").read_text(encoding="utf-8")

STUBS = r"""
const window = globalThis;
const log = [];
const node = (name) => ({ name, __zoom: { x: 0, y: 0, k: 1 }, querySelector: (sel) => ({ sel, in: name }) });
let focused = null;
//: A small element: children, attributes, listeners, and `[data-wb-layer]` lookup.
function fakeEl(tag, name) {
  const el = {
    tag, name: name || tag, children: [], attrs: {}, listeners: [], parent: null, className: "", tabIndex: -1,
    __zoom: { x: 0, y: 0, k: 1 },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    append(...kids) { for (const c of kids) { c.parent = this; this.children.push(c); } },
    remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } },
    addEventListener(type, fn) { this.listeners.push([type, fn]); },
    removeEventListener(type, fn) { const i = this.listeners.findIndex((l) => l[0] === type && l[1] === fn); if (i >= 0) this.listeners.splice(i, 1); },
    fire(type) { for (const [t, fn] of [...this.listeners]) if (t === type) fn({ type }); },
    querySelector(sel) {
      const want = /data-wb-layer="([^"]+)"/.exec(sel)?.[1];
      const walk = (e) => { for (const c of e.children) { if (c.attrs["data-wb-layer"] === want) return c; const r = walk(c); if (r) return r; } return null; };
      return walk(this);
    },
    focus() { focused = this; },
    contains(other) { for (let e = other; e; e = e.parent) if (e === this) return true; return false; },
  };
  return el;
}
const PAGE_EL = Object.assign(fakeEl("div", "page"), { querySelector: (sel) => ({ sel, in: "page" }) });
const document = {
  getElementById: (id) => (id === "whiteboard-container" ? PAGE_EL : { id, in: "page" }),
  createElement: (tag) => fakeEl(tag),
  createElementNS: (ns, tag) => fakeEl(tag),
};
//: d3-zoom's shape, enough of it: a behaviour is a function a selection calls,
//: with getter-setters and a listener table; a transform lives on the element.
function fakeZoom() {
  const conf = { scaleExtent: [0, Infinity], wheelDelta: null, filter: null, clickDistance: 0, tapDistance: 10, duration: 250 };
  const listeners = {};
  const zoom = (sel) => { zoom.bound.push(sel.node()); };
  zoom.bound = [];
  zoom.listeners = listeners;
  for (const key of Object.keys(conf)) zoom[key] = (...a) => (a.length ? ((conf[key] = a[0]), zoom) : conf[key]);
  zoom.on = (name, ...a) => (a.length ? ((listeners[name] = a[0]), zoom) : listeners[name]);
  zoom.transform = (sel, t) => { sel.node().__zoom = t; };
  return zoom;
}
const d3 = {
  zoom: fakeZoom,
  zoomTransform: (n) => n.__zoom,
  select: (n) => {
    const sel = { node: () => n, call(fn, ...a) { fn(sel, ...a); return sel; }, on(name, v) { log.push(["on", n.name, name, v]); return sel; } };
    return sel;
  },
};
const handlerCalls = [];
const wheel = () => 1, filt = () => true;
let wbZoom = d3.zoom().scaleExtent([0.1, 4]).wheelDelta(wheel).filter(filt)
  .on("zoom", (e) => handlerCalls.push(["zoom", window.currentBoardId, e.transform]))
  .on("start.companion", () => handlerCalls.push(["start", window.currentBoardId]))
  .on("end.shield", () => handlerCalls.push(["end", window.currentBoardId]));
const PAGE_ZOOM = wbZoom;
let wbState = { nodes: [{ id: 1 }], sketches: [], objects: [{ id: 10, kind: "sticky" }] };
let wbSelectedItem = { kind: "object", id: 10 };
const wbMultiSelection = new Set(["object:10", "node:1"]);
let wbUndoStack = [{ action: "create", kind: "object", id: 10 }];
let wbRedoStack = [];
let wbHistoryBoard = null;
window.currentBoardId = 1;
let wbRenderQueued = false, wbRenderFrame = 0, wbInitialized = true;
const renders = [];
function wbScheduleRender() { log.push(["schedule", window.currentBoardId]); }
function renderWhiteboardNow() {
  const c = window.wbInstances.container();
  renders.push({ board: window.currentBoardId, into: c.name, layer: Boolean(window.wbInstances.layer("wb-html-layer")), objects: wbState.objects.length, map: window.wbMapState });
}
//: The server: every read is a fresh copy, as a real response is.
const server = { 5: { nodes: [], sketches: [], objects: [{ id: 50, kind: "sticky" }] } };
async function apiJson(url) { const id = Number(/board_id=(\d+)/.exec(url)?.[1]); return JSON.parse(JSON.stringify(server[id])); }
async function wbRefreshMapState(forId) { return forId === undefined ? "LIVE-WRITE" : { type: "board", for: forId }; }
window.wbMapState = { type: "page" };
function wbCancelBoardTimers() { log.push(["cancel", window.currentBoardId]); return undefined; }
function wbUpdateUndoRedoButtons() { log.push(["buttons", wbUndoStack.length]); }
function wbClearMapNodeSizeCache() { log.push(["sizes"]); }
const wbItemElCache = new Map([["x", 1]]);
const wbItemElIndex = { count: 4 };
const wbBoardBgCache = { sig: "s", pass: true };
const wbNavState = { stale: false };
const wbLinkParseCache = new Map([["y", 1]]);
//: The board's own undo, its shape: it pops the active stack, pushes redo and
//: edits the active state, all through the globals.
function undo() {
  const entry = wbUndoStack.pop();
  if (!entry) return;
  wbRedoStack.push(entry);
  wbState.objects = wbState.objects.filter((o) => o.id !== entry.id);
}
const snap = () => JSON.parse(JSON.stringify({
  state: wbState, board: window.currentBoardId, selected: wbSelectedItem, multi: [...wbMultiSelection].sort(),
  undo: wbUndoStack, redo: wbRedoStack,
}));
"""


def _run(body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    tail = "" if "process.exit(0)" in body else "\nprocess.stdout.write(JSON.stringify(out));\n"  # an async body writes its own
    script = STUBS + SRC + "\nconst I = window.wbInstances;\nconst out = {};\n" + body + tail
    got = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_default_instance_is_the_page_board():
    out = _run("""
out.activeIsPage = I.active === I.page;
out.pageZoomIsTheBoardZoom = I.page.zoom === PAGE_ZOOM;
out.container = I.container().name;
out.layer = I.layer("wb-html-layer");
out.listed = I.list.length === 1 && I.list[0] === I.page;
out.again = I.activate(I.page) === undefined && log.length === 0;
out.snap = snap();
""")
    assert out["activeIsPage"] and out["pageZoomIsTheBoardZoom"] and out["listed"]
    assert out["container"] == "page"
    assert out["layer"] == {"id": "wb-html-layer", "in": "page"}
    #: Activating the active instance does nothing: no timer is cancelled, no cache is dropped.
    assert out["again"]
    assert out["snap"]["board"] == 1 and out["snap"]["multi"] == ["node:1", "object:10"]


def test_two_instances_keep_separate_state_selection_undo_and_zoom():
    out = _run("""
const el = node("embed");
const B = I.mount(el, 7);
out.bound = B.zoom.bound.map((n) => n.name);
out.ownZoom = B.zoom !== PAGE_ZOOM;
out.dblclickOff = log.some((r) => r[0] === "on" && r[1] === "embed" && r[2] === "dblclick.zoom" && r[3] === null);
out.copied = [B.zoom.scaleExtent(), B.zoom.wheelDelta() === wheel, B.zoom.filter() === filt];
I.activate(B);
out.b0 = snap();
out.bContainer = I.container().name;
out.bLayer = I.layer("wb-zoom-group");
wbState.objects.push({ id: 20, kind: "sticky" });
wbSelectedItem = { kind: "object", id: 20 };
wbMultiSelection.add("object:20");
wbUndoStack.push({ action: "create", kind: "object", id: 20 });
d3.select(I.container()).call(wbZoom.transform, { x: 5, y: 6, k: 2 });
I.activate(I.page);
out.a = snap();
out.aZoom = d3.zoomTransform(I.container());
out.aZoomIsPage = wbZoom === PAGE_ZOOM;
out.bZoom = d3.zoomTransform(el);
out.bSaved = { objects: B.state.objects, selected: B.selectedItem, multi: [...B.multiSelection], undo: B.undoStack.length, board: B.boardId };
""")
    assert out["bound"] == ["embed"] and out["ownZoom"] and out["dblclickOff"]
    assert out["copied"] == [[0.1, 4], True, True]
    #: A fresh instance starts empty, on its own board.
    assert out["b0"] == {"state": {"nodes": [], "sketches": [], "objects": []}, "board": 7, "selected": None, "multi": [], "undo": [], "redo": []}
    assert out["bContainer"] == "embed"
    assert out["bLayer"] == {"sel": '[data-wb-layer="wb-zoom-group"]', "in": "embed"}
    assert out["a"]["state"]["objects"] == [{"id": 10, "kind": "sticky"}]
    assert out["a"]["selected"] == {"kind": "object", "id": 10}
    assert out["a"]["multi"] == ["node:1", "object:10"]
    assert out["a"]["undo"] == [{"action": "create", "kind": "object", "id": 10}]
    assert out["a"]["board"] == 1
    assert out["aZoom"] == {"x": 0, "y": 0, "k": 1} and out["aZoomIsPage"]
    assert out["bZoom"] == {"x": 5, "y": 6, "k": 2}
    assert out["bSaved"] == {"objects": [{"id": 20, "kind": "sticky"}], "selected": {"kind": "object", "id": 20}, "multi": ["object:20"], "undo": 1, "board": 7}


def test_activating_a_then_b_then_a_restores_a_exactly():
    out = _run("""
const before = snap();
const beforeState = wbState, beforeUndo = wbUndoStack, beforeSel = wbSelectedItem;
const B = I.mount(node("embed"), 7);
I.activate(B);
wbState.nodes.push({ id: 2 });
I.activate(I.page);
out.same = JSON.stringify(snap()) === JSON.stringify(before);
out.identity = wbState === beforeState && wbUndoStack === beforeUndo && wbSelectedItem === beforeSel && wbZoom === PAGE_ZOOM;
I.activate(B);
out.bKept = wbState.nodes;
out.log = log.filter((r) => r[0] !== "on");
out.caches = [wbItemElCache.size, wbItemElIndex.count, wbBoardBgCache.sig, wbBoardBgCache.pass, wbNavState.stale, wbLinkParseCache.size];
""")
    assert out["same"] and out["identity"]
    assert out["bKept"] == [{"id": 2}]
    #: Each switch calls off the outgoing board's timers and frames while its globals
    #: are still live, refreshes the Undo buttons for the incoming stack, and drops
    #: the element and size caches that answer for the other board's DOM.
    assert out["log"] == [
        ["cancel", 1], ["sizes"], ["buttons", 0],
        ["cancel", 7], ["sizes"], ["buttons", 1],
        ["cancel", 1], ["sizes"], ["buttons", 0],
    ]
    assert out["caches"] == [0, -1, "", False, True, 0]


def test_undo_in_b_never_touches_a():
    out = _run("""
const B = I.mount(node("embed"), 7);
I.activate(B);
wbState.objects.push({ id: 30, kind: "sticky" });
wbUndoStack.push({ action: "create", kind: "object", id: 30 });
undo();
undo(); // B's stack is empty now: a second undo must not reach into A's
out.b = snap();
I.activate(I.page);
out.a = snap();
""")
    assert out["b"]["state"]["objects"] == [] and out["b"]["undo"] == [] and out["b"]["redo"] == [{"action": "create", "kind": "object", "id": 30}]
    assert out["a"]["state"]["objects"] == [{"id": 10, "kind": "sticky"}]
    assert out["a"]["undo"] == [{"action": "create", "kind": "object", "id": 10}] and out["a"]["redo"] == []


def test_a_gesture_on_an_instance_activates_it_first():
    """A zoom event from an embed's own container runs the board's one handler with
    that embed's globals live, so a pan in a document never moves the page board."""
    out = _run("""
const B = I.mount(node("embed"), 7);
B.zoom.on("start.companion")({});
B.zoom.on("zoom")({ transform: { k: 3 } });
out.active = I.active === B;
out.calls = handlerCalls;
""")
    assert out["active"]
    assert out["calls"] == [["start", 7], ["zoom", 7, {"k": 3}]]


def test_unmount_returns_to_the_page_board():
    out = _run("""
const el = node("embed");
const B = I.mount(el, 7);
I.activate(B);
I.unmount(B);
out.active = I.active === I.page;
out.listed = I.list.length;
out.board = window.currentBoardId;
out.zoomOff = log.some((r) => r[0] === "on" && r[1] === "embed" && r[2] === ".zoom" && r[3] === null);
let threw = false;
try { I.unmount(I.page); } catch (e) { threw = true; }
out.pageStays = threw && I.list.length === 1;
""")
    assert out["active"] and out["listed"] == 1 and out["board"] == 1 and out["zoomOff"] and out["pageStays"]


def test_the_copied_zoom_knows_every_setting_the_page_zoom_has():
    """An embed's behaviour is built from the page's, so a setting or listener added
    to `wbZoom` in whiteboard.js has to be one the copy carries."""
    wb = (JS / "whiteboard.js").read_text(encoding="utf-8")
    chain = wb[wb.index("let wbZoom = d3") : wb.index(";", wb.index("let wbZoom = d3"))]
    methods = set(re.findall(r"\.(\w+)\(", chain)) - {"zoom", "on"}
    copied = set(re.search(r"const ZOOM_SETTINGS = \[([^\]]*)\]", SRC).group(1).replace('"', "").replace(" ", "").split(","))
    assert methods <= copied, methods - copied
    events = set(re.findall(r'\.on\("([\w.]+)"', chain))
    listed = set(re.search(r"const ZOOM_EVENTS = \[([^\]]*)\]", SRC).group(1).replace('"', "").replace(" ", "").split(","))
    assert events == listed
    assert "wbZoom.on(" not in "".join(p.read_text(encoding="utf-8") for p in JS.glob("whiteboard*.js")), "a listener added later would not be copied"


#: Board files that may still name the page container: the instance file resolves
#: the default from it, and initWhiteboard binds the page's own listeners to it.
_CONTAINER_LOOKUP = re.compile(r'getElementById\("whiteboard-container"\)')
_LAYER_LOOKUP = re.compile(r'(?:getElementById\("|\$\("|select\("#)(wb-svg-layer|wb-zoom-group|wb-html-layer|wb-overlay-layer|wb-overlay-zoom-group)"\)')


def test_board_code_finds_its_container_and_layers_through_the_active_instance():
    left = {}
    for path in sorted(JS.glob("whiteboard*.js")):
        if path.name == "whiteboard-instances.js":
            continue
        #: A load-time `onSurface("board", ...)` wiring runs before whiteboard-instances.js
        #: has loaded and binds the page board's own element: marked "page wiring", it may
        #: name it (measured: three, in whiteboard.js, -library.js and -interchange.js).
        text = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if "// page wiring, at load" not in line)
        hits = len(_CONTAINER_LOOKUP.findall(text)) + len(_LAYER_LOOKUP.findall(text))
        if hits:
            left[path.name] = hits
    #: whiteboard-options.js drew the page view into `$("wb-zoom-group")`, the page's
    #: only; it draws into the active board's zoom group since L-whiteboard-56, and
    #: its group is a class, since an id can appear once on a page.
    assert left == {}, left
    assert 'const PAGE_CONTAINER = "whiteboard-container";' in SRC and "document.getElementById(PAGE_CONTAINER)" in SRC


def test_two_live_embeds_of_one_board_stay_independent():
    """The mount API documents builds to: `wbInstance.create(host, boardId, { editable })`."""
    out = _run("""
(async () => {
const hostA = fakeEl("div", "hostA"), hostB = fakeEl("div", "hostB");
const a = await window.wbInstance.create(hostA, 5, { editable: true });
const b = await window.wbInstance.create(hostB, 5, {});
const A = a.instance, B = b.instance;
out.afterCreate = { active: I.active === I.page, board: window.currentBoardId, map: window.wbMapState, objects: wbState.objects.length };
out.renders = renders.slice();
out.drawnInHost = [hostA.children[0].children.length, hostB.children[0].children.length];
out.editable = [A.editable, B.editable];
// A gesture in A makes it live; edit, select, undo and zoom there.
A.container.fire("pointerdown");
out.aLive = I.active === A && window.currentBoardId === 5;
wbState.objects.push({ id: 51, kind: "sticky" });
wbSelectedItem = { kind: "object", id: 51 };
wbMultiSelection.add("object:51");
wbUndoStack.push({ action: "create", kind: "object", id: 51 });
d3.select(I.container()).call(wbZoom.transform, { x: 9, y: 9, k: 3 });
B.container.fire("focusin");
out.b = snap();
out.bZoom = d3.zoomTransform(B.container);
undo();
out.bAfterUndo = { objects: wbState.objects.length, undo: wbUndoStack.length };
A.container.fire("pointerdown");
out.a = snap();
out.aZoom = d3.zoomTransform(A.container);
PAGE_EL.fire("pointerdown");
out.page = snap();
out.pageZoom = d3.zoomTransform(PAGE_EL);
out.pageMap = window.wbMapState;
process.stdout.write(JSON.stringify(out));
process.exit(0);
})();
""")
    assert out["afterCreate"] == {"active": True, "board": 1, "map": {"type": "page"}, "objects": 1}
    #: Each embed was drawn into its own container with its own globals, and the page board is drawn again after.
    assert [r["into"] for r in out["renders"]] == ["div", "div"]
    assert all(r["board"] == 5 and r["layer"] and r["objects"] == 1 and r["map"] == {"type": "board", "for": 5} for r in out["renders"])
    assert out["drawnInHost"] == [3, 3]
    assert out["editable"] == [True, False]
    assert out["aLive"]
    assert out["b"]["state"]["objects"] == [{"id": 50, "kind": "sticky"}]
    assert out["b"]["selected"] is None and out["b"]["multi"] == [] and out["b"]["undo"] == []
    assert out["bZoom"] == {"x": 0, "y": 0, "k": 1}
    assert out["bAfterUndo"] == {"objects": 1, "undo": 0}
    assert out["a"]["state"]["objects"] == [{"id": 50, "kind": "sticky"}, {"id": 51, "kind": "sticky"}]
    assert out["a"]["selected"] == {"kind": "object", "id": 51} and out["a"]["multi"] == ["object:51"] and len(out["a"]["undo"]) == 1
    assert out["aZoom"] == {"x": 9, "y": 9, "k": 3}
    assert out["page"]["board"] == 1 and out["page"]["state"]["objects"] == [{"id": 10, "kind": "sticky"}]
    assert out["page"]["multi"] == ["node:1", "object:10"] and len(out["page"]["undo"]) == 1
    assert out["pageZoom"] == {"x": 0, "y": 0, "k": 1} and out["pageMap"] == {"type": "page"}


def test_destroy_leaves_nothing_behind_and_twice_is_safe():
    out = _run("""
(async () => {
const host = fakeEl("div", "host"), other = fakeEl("div", "other");
const a = await window.wbInstance.create(host, 5, {});
const b = await window.wbInstance.create(other, 5, {});
out.pageListenersWhileEmbeds = PAGE_EL.listeners.length;
const box = a.instance.container;
let calls = 0;
const off = a.onChange(() => calls++);
box.fire("pointerdown");
I.changed();
off();
I.changed();
out.calls = calls;
a.focus();
out.focused = focused === box;
a.destroy();
a.destroy();
out.host = host.children.length;
out.boxListeners = box.listeners.length;
out.zoomOff = log.some((r) => r[0] === "on" && r[1] === box.name && r[2] === ".zoom" && r[3] === null);
out.active = I.active === I.page && window.currentBoardId === 1;
out.listed = I.list.length;
out.pageListenersAfterOne = PAGE_EL.listeners.length;
b.destroy();
out.pageListenersAfterAll = PAGE_EL.listeners.length;
out.end = { list: I.list.length, other: other.children.length };
process.stdout.write(JSON.stringify(out));
process.exit(0);
})();
""")
    assert out["pageListenersWhileEmbeds"] == 3
    assert out["calls"] == 1 and out["focused"]
    assert out["host"] == 0 and out["boxListeners"] == 0 and out["zoomOff"] and out["active"]
    assert out["listed"] == 2 and out["pageListenersAfterOne"] == 3
    assert out["pageListenersAfterAll"] == 0 and out["end"] == {"list": 1, "other": 0}


def test_load_time_wiring_never_asks_for_the_active_instance():
    """Found by the drive: `onSurface("board", ...)` runs its body at once when the
    board's template is already built, which is before whiteboard-instances.js has
    loaded, so a `wbInstances` read there threw and stopped whiteboard.js loading."""
    found = []
    for path in sorted(JS.glob("whiteboard*.js")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"^(\s*)onSurface\(", line)
            if not m or line.rstrip().endswith(");"):
                continue
            body = len(m.group(1)) + 2
            for j in range(i + 1, len(lines)):
                if lines[j].startswith(m.group(1) + "}"):
                    break
                if "wbInstances." in lines[j] and len(lines[j]) - len(lines[j].lstrip()) == body:
                    found.append(f"{path.name}:{j + 1}")
    assert found == [], found


#: A board edit the way initWhiteboard's handlers make one, through the live globals:
#: it adds a card to the active state, records it (wbPushUndo's tail is
#: `wbInstances.changed()`), and saves to the active board.
_EDITING = """
const saves = [], seen = [];
let nextId = 100;
function wbPushUndo(entry) { wbUndoStack.push(entry); wbRedoStack = []; I.changed(); }
I.on("pointerdown", function () {
  seen.push([window.currentBoardId, I.container().name]);
  const id = nextId++;
  wbState.objects.push({ id, kind: "sticky" });
  wbPushUndo({ action: "create", kind: "object", id });
  saves.push({ board: window.currentBoardId, into: I.container().name, objects: wbState.objects.map((o) => o.id) });
});
I.on("keydown", () => undo());
I.on("wheel", () => seen.push(["wheel", window.currentBoardId, I.container().name]), { passive: false }, true);
"""


def test_two_editable_embeds_of_one_board_edit_undo_and_save_independently():
    """L-whiteboard-54: initWhiteboard's handlers are bound per instance container,
    and the one that hears an event makes its own instance live first."""
    out = _run(_EDITING + """
(async () => {
out.pageListeners = PAGE_EL.listeners.length;
const hostA = fakeEl("div", "hostA"), hostB = fakeEl("div", "hostB");
const a = await window.wbInstance.create(hostA, 5, { editable: true });
const b = await window.wbInstance.create(hostB, 5, { editable: true });
hostA.children[0].name = "boxA"; hostB.children[0].name = "boxB";
const A = a.instance, B = b.instance;
const fired = { a: 0, b: 0 };
a.onChange(() => fired.a++);
b.onChange(() => fired.b++);
A.container.fire("pointerdown");
A.container.fire("pointerdown");
B.container.fire("pointerdown");
A.container.fire("keydown");
out.aLive = snap();
B.container.fire("wheel");
out.b = snap();
A.container.fire("focusin");
out.a = snap();
PAGE_EL.fire("pointerdown");
out.page = snap();
out.saves = saves;
out.seen = seen;
out.fired = fired;
process.stdout.write(JSON.stringify(out));
process.exit(0);
})();
""")
    #: The page board gets its own copy of each handler, as before: one listener per `on`.
    assert out["pageListeners"] == 3
    assert out["seen"] == [[5, "boxA"], [5, "boxA"], [5, "boxB"], ["wheel", 5, "boxB"], [1, "page"]]
    assert out["saves"] == [
        {"board": 5, "into": "boxA", "objects": [50, 100]},
        {"board": 5, "into": "boxA", "objects": [50, 100, 101]},
        {"board": 5, "into": "boxB", "objects": [50, 102]},
        {"board": 1, "into": "page", "objects": [10, 103]},
    ]
    #: Undo in A took back A's last card only; B kept its own card and stack.
    assert [o["id"] for o in out["aLive"]["state"]["objects"]] == [50, 100] and [e["id"] for e in out["aLive"]["redo"]] == [101]
    assert [o["id"] for o in out["b"]["state"]["objects"]] == [50, 102] and [e["id"] for e in out["b"]["undo"]] == [102] and out["b"]["redo"] == []
    assert [o["id"] for o in out["a"]["state"]["objects"]] == [50, 100] and [e["id"] for e in out["a"]["undo"]] == [100]
    assert [o["id"] for o in out["page"]["state"]["objects"]] == [10, 103] and out["page"]["board"] == 1
    #: onChange fires once per recorded edit, on the instance edited only.
    assert out["fired"] == {"a": 2, "b": 1}


def test_a_read_only_embed_pans_and_zooms_only_and_destroy_unbinds_every_handler():
    out = _run(_EDITING + """
(async () => {
const hostA = fakeEl("div", "hostA"), hostR = fakeEl("div", "hostR");
const a = await window.wbInstance.create(hostA, 5, { editable: true });
const r = await window.wbInstance.create(hostR, 5, {});
const boxA = a.instance.container, boxR = r.instance.container;
out.classes = [boxA.className, boxR.className];
out.counts = { a: boxA.listeners.length, r: boxR.listeners.length, aBound: a.instance.listeners.length, rBound: r.instance.listeners.length };
let changes = 0;
r.onChange(() => changes++);
boxR.fire("pointerdown");
boxR.fire("keydown");
boxR.fire("wheel");
out.readOnly = { saves: saves.length, changes, seen, objects: wbState.objects.length, live: I.active === r.instance };
const f = r.instance.zoom.filter();
out.filter = [f === filt, f({ type: "mousedown", button: 0 }), f({ type: "mousedown", button: 2 }), f({ type: "wheel" }), a.instance.zoom.filter() === filt];
//: Registered after the embeds exist (initWhiteboard runs late): bound to both at once.
I.on("dblclick", () => seen.push("dbl"));
out.late = [boxA.listeners.length, boxR.listeners.length, PAGE_EL.listeners.length];
a.destroy();
a.destroy();
r.destroy();
out.after = { a: boxA.listeners.length, r: boxR.listeners.length, aBound: a.instance.listeners.length, page: PAGE_EL.listeners.length };
process.stdout.write(JSON.stringify(out));
process.exit(0);
})();
""")
    assert out["classes"] == ["whiteboard-container wb-embed", "whiteboard-container wb-embed wb-embed-readonly"]
    #: Editable: its three handlers plus the two wake listeners; read-only: the wheel pan and the two wakes.
    assert out["counts"] == {"a": 5, "r": 3, "aBound": 3, "rBound": 1}
    assert out["readOnly"] == {"saves": 0, "changes": 0, "seen": [["wheel", 5, "div"]], "objects": 1, "live": True}
    #: Any plain drag pans a read-only board; the wheel keeps the page's own rule.
    assert out["filter"] == [False, True, False, True, True]
    #: The page's three plus the late one; the embeds' wake listeners on the page while they live.
    assert out["late"] == [6, 3, 3 + 1 + 3]
    assert out["after"] == {"a": 0, "r": 0, "aBound": 0, "page": 4}


def test_init_whiteboard_binds_container_listeners_through_the_instances():
    """No handler in the board files is bound to the page container directly, so
    none is missing from an embed (L-whiteboard-54)."""
    text = "".join(p.read_text(encoding="utf-8") for p in sorted(JS.glob("whiteboard*.js")))
    direct = re.findall(r'(?:containerEl|container\.node\(\)\??|wbInstances\.container\(\)\??|\$\("whiteboard-container"\)\??)\.addEventListener\(', text)
    assert direct == [], direct
    wb = (JS / "whiteboard.js").read_text(encoding="utf-8")
    assert not re.search(r"^(?!\s*//).*\bcontainerEl\b", wb, re.M)
    assert wb.count("wbInstances.on(") >= 26
    #: The document-wide key handler asks whose board a key is for, and a read-only one takes none.
    assert "const embed = wbInstances.embedFor(e.target);" in wb and "embed ? !embed.editable" in wb
    cmds = (JS / "whiteboard-commands.js").read_text(encoding="utf-8")
    assert "wbInstances.embedFor(document.activeElement)" in cmds
    #: In the boards bundle's stylesheet, which loads with the embed, not the boot CSS (its budget, 2026-11-14).
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".wb-embed-readonly > [data-wb-layer] {\n  pointer-events: none;" in css


def test_board_selectors_search_the_active_board_only():
    """L-whiteboard-55: `#wb-html-layer .wb-object` and the other board lookups are
    searched in the active board's container; an embed's layer ids read as its
    `data-wb-layer`, and the page board's selector is the one it always was."""
    out = _run("""
const el = node("embed");
el.querySelectorAll = (sel) => [{ sel, in: "embed" }];
PAGE_EL.querySelectorAll = (sel) => [{ sel, in: "page" }];
out.page = [I.query("#wb-html-layer .wb-object"), I.queryAll("#wb-zoom-group > g.sketch-group, #wb-html-layer > svg")];
const B = I.mount(el, 7);
I.activate(B);
out.embed = [
  I.query('#wb-html-layer .wb-object[data-id="3"]'),
  I.queryAll("#wb-zoom-group > .wb-sketch-handle-group, #wb-overlay-zoom-group > .wb-sketch-handle-group"),
  I.query('.sketch-group[data-id="4"]'),
  I.query("#wb-html-layer-x, #wb-sidebar"),
];
""")
    assert out["page"] == [
        {"sel": "#wb-html-layer .wb-object", "in": "page"},
        [{"sel": "#wb-zoom-group > g.sketch-group, #wb-html-layer > svg", "in": "page"}],
    ]
    assert out["embed"] == [
        {"sel": '[data-wb-layer="wb-html-layer"] .wb-object[data-id="3"]', "in": "embed"},
        [{"sel": '[data-wb-layer="wb-zoom-group"] > .wb-sketch-handle-group, [data-wb-layer="wb-overlay-zoom-group"] > .wb-sketch-handle-group', "in": "embed"}],
        {"sel": '.sketch-group[data-id="4"]', "in": "embed"},
        #: Only the board's own layer ids are rewritten.
        {"sel": "#wb-html-layer-x, #wb-sidebar", "in": "embed"},
    ]


def test_no_board_file_looks_up_a_layer_or_an_item_document_wide():
    layer = r"#wb-(?:svg-layer|zoom-group|shapes-group|lines-group|strokes-group|html-layer|overlay-layer|overlay-zoom-group)"
    wide = re.compile(r"document\.querySelector(?:All)?\(\s*[`\"'](?:" + layer + r"|\.wb-object|\.sketch-group\[|\.node-card|\.wb-map-node|\.wb-map-edges|\[data-id)")
    found = {}
    for path in sorted(JS.glob("whiteboard*.js")):
        hits = len(wide.findall(path.read_text(encoding="utf-8")))
        if hits:
            found[path.name] = hits
    assert found == {}, found
    wb = (JS / "whiteboard.js").read_text(encoding="utf-8")
    assert 'd3.select(wbInstances.query(outlineOnly ? "#wb-zoom-group" : "#wb-overlay-zoom-group"))' in wb
    assert "d3.select(wbInstances.query(layer))" in wb


def test_each_board_keeps_its_own_inverse_zoom():
    """L-whiteboard-56: the grips' `--wb-inv-zoom` is written per board, an embed's
    scoped to its own box, so a zoomed embed never resizes the page board's grips
    (or the reverse); the far-zoom rules that read it name an embed too."""
    wb = (JS / "whiteboard.js").read_text(encoding="utf-8")
    grips = re.search(r"const WB_INV_ZOOM_GRIPS = \[.*?\];", wb, re.S).group(0)
    rules = wb[wb.index("function wbInvZoomRules()") :]
    rules = rules[: rules.index("\n}\n") + 3]
    publish = wb[wb.index("function wbSyncGridToTransform(") :]
    publish = publish[: publish.index("\n}\n") + 3]
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = grips + rules + """
const page = { container: null, invZoom: "1" };
const a = { container: {}, key: 2, invZoom: "0.5" }, b = { container: {}, key: 3, invZoom: "4" };
const wbInstances = { list: [page, a, b] };
process.stdout.write(JSON.stringify(wbInvZoomRules().split("\\n")));
"""
    got = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    out = json.loads(got.stdout)
    assert len(out) == 3
    assert out[0].startswith(".wb-object-frame .wb-frame-title, ") and out[0].endswith("{ --wb-inv-zoom: 1; }")
    assert out[1].startswith('[data-wb-embed="2"] :is(.wb-object-frame .wb-frame-title, ') and out[1].endswith(") { --wb-inv-zoom: 0.5; }")
    assert out[2].startswith('[data-wb-embed="3"] :is(') and out[2].endswith(") { --wb-inv-zoom: 4; }")
    #: The value, the timer and the attribute are the instance's, not one global.
    assert "const inst = wbInstances.active;" in publish and "inst.invTimer = setTimeout(() => wbPublishInvZoom(el, inv, inst), 120);" in publish
    assert "wbInvZoomValue" not in wb and "wbInvZoomTimer" not in wb
    assert '".wb-embed[data-wb-zoom-far] .wb-map-actions"' in grips
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".wb-embed[data-wb-zoom-far] .wb-map-ref {" in css and ".wb-embed[data-wb-zoom-far] .wb-map-node:not(.wb-selected) .wb-map-collapse {" in css
    assert 'box.setAttribute("data-wb-embed", String(inst.key));' in SRC
    opts = (JS / "whiteboard-options.js").read_text(encoding="utf-8")
    assert 'const zoom = wbInstances.layer("wb-zoom-group");' in opts


def _wb_functions(*names: str) -> str:
    """whiteboard.js's own text for each named top-level function or const."""
    wb = (JS / "whiteboard.js").read_text(encoding="utf-8")
    parts = []
    for name in names:
        at = re.search(rf"^(?:async function|function|const) {name}\b", wb, re.M).start()
        end = wb.index("\n}\n", at) + 3 if not wb.startswith("const", at) else wb.index(";\n", at) + 2
        parts.append(wb[at:end])
    return "\n".join(parts)


def test_a_multi_row_save_goes_to_the_board_it_started_on():
    """L-whiteboard-57: a nudge save of several rows awaits a topic still being
    created, then saves the rest; another board activated in between (a gesture
    on an embed, which flushes the nudge and swaps the globals) must not take the
    later rows, nor reload in the outgoing board's place when the batch fails."""
    fns = _wb_functions("wbSaveNode", "wbSaveMany", "WB_SAVE_MANY_MAX", "wbSaveManyBatch", "wbSaveRow")
    out = _run(fns + """
const puts = [], reloads = [];
let release, failBatch = false;
const gate = new Promise((r) => { release = r; });
apiJson = async (url, opts) => {
  if (opts?.method === "PUT") {
    puts.push({ url, body: JSON.parse(opts.body) });
    if (failBatch && url.endsWith("save-many")) throw new Error("409");
    return {};
  }
  return { nodes: [], sketches: [], objects: [] };
};
async function wbSaveObject(d) { await gate; puts.push({ url: "object " + d.id, board: window.currentBoardId }); }
async function wbSaveSketchProps() {}
async function fetchWhiteboardState() { reloads.push(window.currentBoardId); }
function recordBrowserLog() {}
const WB_KIND_INFO = { node: { list: "nodes", payload: (n) => ({ x: n.x }) }, object: { list: "objects", payload: (o) => ({ x: o.x }) } };
(async () => {
const embed = I.mount(fakeEl("div", "box"), 5);
const creating = { id: 20, _creating: true };
const saving = wbSaveMany([{ kind: "object", item: creating }, { kind: "node", item: { id: 7, entry_id: 3, x: 1, y: 2 } }]);
I.activate(embed);
out.mid = window.currentBoardId;
release();
await saving;
out.puts = puts;
failBatch = true;
I.activate(I.page);
const batch = wbSaveMany([{ kind: "node", item: { id: 8, x: 1 } }, { kind: "object", item: { id: 9, x: 2 } }]);
I.activate(embed);
out.batchOk = await batch;
out.reloads = reloads;
process.stdout.write(JSON.stringify(out));
process.exit(0);
})();
""")
    assert out["mid"] == 5
    node_put = next(p for p in out["puts"] if p["url"] == "/whiteboard/nodes/7")
    assert node_put["body"]["board_id"] == 1, out["puts"]
    #: The failed batch belonged to the page board; the embed now live is not reloaded in its place.
    assert out["batchOk"] is False and out["reloads"] == [], out["reloads"]


def test_an_embed_draw_leaves_the_page_board_chrome_alone():
    """L-whiteboard-58: the board's one render also writes page-wide chrome (the
    empty hint and cue, the board picker's count, the navigator, the outline).
    An embed's draw writes none of it, and so no longer redraws the page board
    after itself to put that chrome back."""
    wb = (JS / "whiteboard.js").read_text(encoding="utf-8")
    marks = (JS / "whiteboard-map-marks.js").read_text(encoding="utf-8")
    now = wb[wb.index("function renderWhiteboardNow() {") :]
    now = now[: now.index("\n}\n") + 3]
    after = marks[marks.index("  function wbMapAfterRender() {") :]
    after = after[: after.index("\n  }\n") + 5]
    out = _run(now + after + """
const calls = [];
for (const name of ["renderWhiteboard", "wbUpdateSelectionBar", "wbApplySearchHighlight", "wbRenderNavigator", "wbSyncBoardCount", "wbOutlineSync", "wbMapPaintMarkerFilter"]) {
  globalThis[name] = () => calls.push([name, window.currentBoardId]);
}
const wbMarkerUi = { filters: new Set(["x"]) }, wbMapDim = { on: false };
const inst = I.mount(fakeEl("div", "box"), 5);
renderWhiteboardNow();
out.page = calls.splice(0);
I.activate(inst);
renderWhiteboardNow();
out.embed = calls.splice(0);
""")
    page_names = [c[0] for c in out["page"]]
    embed_names = [c[0] for c in out["embed"]]
    assert {"wbRenderNavigator", "wbSyncBoardCount", "wbOutlineSync"} <= set(page_names), page_names
    #: The embed's own board is drawn, highlighted and filtered; the page's panels are not touched.
    assert embed_names == ["renderWhiteboard", "wbApplySearchHighlight", "wbMapPaintMarkerFilter"], embed_names
    assert all(c[1] == 5 for c in out["embed"])
    #: The empty hint and cue are the page board's: an embed's render leaves them be.
    render = wb[wb.index("function renderWhiteboard() {") :]
    hint = render[: render.index('document.getElementById("wb-empty-cue")')]
    assert "if (!wbInstances.active.container) {" in hint[hint.rindex("const wbHintHidden") :]
    #: And draw() puts nothing back, so it schedules no page render after itself.
    #: draw() is drawEmbed() since the bundle lints read generic private names as globals (CI on 4cf588e0).
    draw = SRC[SRC.index("  function drawEmbed(inst) {") :]
    draw = draw[: draw.index("\n  }\n")]
    assert "wbScheduleRender" not in draw


def test_each_board_keeps_its_own_history_across_activations():
    """Found driving L-whiteboard-54 in the app: `wbHistoryFor` keeps each board's
    stacks by board id against one `wbHistoryBoard`, and every activation reaches
    it (wbUpdateUndoRedoButtons), so with that global left on the outgoing board
    the incoming embed's stacks were filed under the page's board and the page
    got them back: Ctrl+Z in the embed popped its step and sent nothing. The key
    is an instance's, swapped with its stacks."""
    wb = (JS / "whiteboard.js").read_text(encoding="utf-8")
    hist = wb[wb.index("const wbHistoryByBoard = new Map();") :]
    hist = hist[: hist.index("function wbHistoryRestore(")].replace("let wbHistoryBoard = null;", "")
    out = _run(hist + """
function wbHistoryRestore(key) {}
wbUpdateUndoRedoButtons = () => wbHistoryFor();
wbHistoryFor();
const inst = I.mount(fakeEl("div", "box"), 5);
I.activate(inst);
wbUndoStack.push({ action: "create", kind: "object", id: 51 });
I.activate(I.page);
wbUndoStack.push({ action: "create", kind: "object", id: 11 });
I.activate(inst);
wbHistoryFor();
out.embed = wbUndoStack.map((e) => e.id);
I.activate(I.page);
wbHistoryFor();
out.page = wbUndoStack.map((e) => e.id);
""")
    assert out["embed"] == [51], out
    #: The page's first read started its board's history afresh (the stub's step 10 was no board's).
    assert out["page"] == [11], out


def test_settings_wiring_finds_the_html_layer_through_the_active_board():
    """L-whiteboard-59: boot code asked the document for `#wb-html-layer`, which
    is the page board's even while an embed is live. `wbInstances.query` searches
    the active board's container and reads the id as its own layer; with the lazy
    bundle not loaded no board, so no map editor, is open."""
    text = (JS / "settings-wiring.js").read_text(encoding="utf-8")
    assert 'window.wbInstances?.query("#wb-html-layer .wb-map-text' in text
    assert 'document.querySelector("#wb-html-layer .wb-map-text' not in text
    out = _run("""
const emb = I.mount(fakeEl("div", "box"), 5);
emb.container.append(Object.assign(fakeEl("div", "html"), { attrs: { "data-wb-layer": "wb-html-layer" } }));
out.page = I.query("#wb-html-layer .wb-map-text");
I.activate(emb);
out.embed = I.query("#wb-html-layer .wb-map-text").name;
""")
    assert out["page"] == {"sel": "#wb-html-layer .wb-map-text", "in": "page"} and out["embed"] == "html"