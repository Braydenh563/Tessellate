"""INBOX 1593: "it is hard to drag notes and other objects into the tray and the
tray popup closes as well when I try to do so". The class, not the case:

- a live drag of any kind never closes a popover (menus.js: one drag flag,
  `dragFlag`, read by the outside click and by
  the scroll closer a drag's own edge scroll fires);
- a drop zone that is the button and the panel with room around them;
- the button springs the tray open under a held drag and puts it back if the
  card went elsewhere;
- every kind of card lands in the tray (the six object kinds, and the chat's
  source cards, which were buttons the drag refused).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests._objmove_node import JS, needs_node, run

FILES = ["obj-ref.js", "obj-clip.js", "obj-drag.js", "obj-reorder.js", "obj-carry.js", "obj-tray.js"]
STUBS = """
const store = {};
globalThis.sessionStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; } };
const toasts = [];
globalThis.toast = (text) => toasts.push(text);
globalThis.offerUndo = () => {};
const rect = (left, top, width, height) => ({ left, top, width, height, right: left + width, bottom: top + height });
function fakeTray({ open = false } = {}) {
  const classes = new Set(open ? [] : ["hidden"]);
  const button = { id: "status-tray", expanded: open ? "true" : "false", clicks: 0,
    getBoundingClientRect: () => rect(1000, 868, 28, 28),
    getAttribute(name) { return name === "aria-expanded" ? this.expanded : null; },
    click() { this.clicks++; this.expanded = this.expanded === "true" ? "false" : "true"; panel.classList.toggle("hidden"); } };
  const panel = { id: "obj-tray", getBoundingClientRect: () => rect(840, 790, 384, 68), classList: { contains: (c) => classes.has(c),
    toggle: (c) => (classes.has(c) ? classes.delete(c) : classes.add(c)) } };
  globalThis.$ = (id) => ({ "status-tray": button, "obj-tray": panel })[id] || null;
  globalThis.objTrayPaint = () => {};
  return { button, panel };
}
"""

MENUS = (JS / "menus.js").read_text(encoding="utf-8")


def _menus_closers() -> str:
    """The drag flag and the page-wide popover closers, cut out of menus.js so a
    stub page can drive them without the other fifteen hundred lines."""
    flag = MENUS[MENUS.index("const dragFlag = (() => {"):MENUS.index("function closeActionMenusOnScroll")]
    closers = MENUS[MENUS.index("const openHelpPopovers = new Set();"):MENUS.index("function wireHelpPopover")]
    return flag + closers


def _page(body: str):
    harness = r"""
const handlers = { doc: {}, win: {} };
const document = { addEventListener: (t, f) => { (handlers.doc[t] = handlers.doc[t] || []).push(f); } };
const window = { addEventListener: (t, f) => { (handlers.win[t] = handlers.win[t] || []).push(f); } };
let now = 1000;
const performance = { now: () => now };
const fire = (where, type, event = {}) => { for (const f of handlers[where][type] || []) f({ detail: 1, target: {}, clientX: 0, clientY: 0, ...event }); };
let closed = 0;
const popover = { panel: { contains: () => false }, trigger: { contains: () => false }, close() { closed++; } };
const reopen = () => { openHelpPopovers.add(popover); };
const placeHelpPopover = () => {};
"""
    code = harness + _menus_closers() + "\n" + body
    proc = subprocess.run(["node", "-e", f"const out = (v) => process.stdout.write(JSON.stringify(v));\n{code}"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout)


@needs_node
def test_the_closers_ignore_a_click_or_a_scroll_during_a_drag_of_any_kind() -> None:
    out = _page("""
    const results = {};
    for (const kind of ["obj", "native"]) {
      reopen(); closed = 0;
      dragFlag.hold(kind);
      fire("doc", "click"); fire("win", "scroll");
      results[kind] = closed;
      dragFlag.release(kind);
    }
    out(results);
    """)
    assert out == {"obj": 0, "native": 0}


@needs_node
def test_the_closers_work_again_once_the_drag_and_its_last_frame_are_over() -> None:
    out = _page("""
    reopen(); closed = 0;
    dragFlag.hold("obj"); dragFlag.release("obj");
    fire("win", "scroll");               // the edge scroll's last event, a frame late
    const tail = closed;
    now += 250;
    fire("doc", "click");                // an ordinary outside click, 250 ms on
    out({ tail, after: closed });
    """)
    assert out == {"tail": 0, "after": 1}


@needs_node
def test_the_browsers_own_drags_hold_the_same_flag() -> None:
    out = _page("""
    reopen(); closed = 0;
    fire("doc", "dragstart");
    const during = dragFlag.active();
    fire("win", "scroll");
    fire("doc", "dragend");
    now += 250;
    out({ during, closed, after: dragFlag.active() });
    """)
    assert out == {"during": True, "closed": 0, "after": False}


@needs_node
def test_a_press_that_travelled_is_a_drag_attempt_not_an_outside_click() -> None:
    out = _page("""
    reopen(); closed = 0;
    fire("doc", "pointerdown", { clientX: 100, clientY: 100 });
    fire("doc", "pointerup", { clientX: 400, clientY: 300 });
    now += 300;
    fire("doc", "click", { clientX: 400, clientY: 300 });
    const dragged = closed;
    fire("doc", "pointerdown", { clientX: 100, clientY: 100 });
    fire("doc", "pointerup", { clientX: 102, clientY: 101 });
    now += 300;
    fire("doc", "click", { clientX: 102, clientY: 101 });
    out({ dragged, clicked: closed });
    """)
    assert out == {"dragged": 0, "clicked": 1}


@needs_node
def test_a_scroll_under_a_held_press_is_the_selection_autoscroll_not_a_hand() -> None:
    out = _page("""
    reopen(); closed = 0;
    fire("doc", "pointerdown", { clientX: 5, clientY: 5 });
    fire("win", "scroll");
    const held = closed;
    fire("doc", "pointerup");
    now += 300;
    fire("win", "scroll");
    out({ held, released: closed });
    """)
    assert out == {"held": 0, "released": 1}


@needs_node
def test_the_drop_zone_is_the_button_and_the_open_panel_with_room_around_them() -> None:
    out = run(FILES, STUBS + """
    fakeTray();
    const closed = { inside: objTrayDoor.hit(1012, 882), nearMiss: objTrayDoor.hit(1012 + 28 / 2 + 10, 882), far: objTrayDoor.hit(900, 800) };
    const area = (zone) => zone.reduce((sum, r) => sum + (r.right - r.left) * (r.bottom - r.top), 0);
    const closedArea = area(objTrayDoor.zone());
    fakeTray({ open: true });
    const open = { panel: objTrayDoor.hit(900, 820), gap: objTrayDoor.hit(1012, 862), nearPanel: objTrayDoor.hit(840 - 5, 820), far: objTrayDoor.hit(100, 100) };
    __out({ closed, closedArea, open, zones: objTrayDoor.zone().length });
    """)
    assert out["closed"] == {"inside": True, "nearMiss": True, "far": False}
    assert out["closedArea"] == 52 * 52, "the 28 px button grown by 12 px each way"
    assert out["open"] == {"panel": True, "gap": True, "nearPanel": True, "far": False}
    assert out["zones"] == 3


@needs_node
def test_a_drop_beside_the_button_still_lands_in_the_tray_but_not_over_another_target() -> None:
    out = run(FILES, STUBS + """
    fakeTray();
    const at = (x, y, el) => { document.elementFromPoint = () => el; return objCarryTarget({ x, y, ref: ref(1) })?.type || null; };
    const ref = (id) => objRef("note", id, `Note ${id}`);
    const composer = { closest: (sel) => (sel.includes("#chat-input") ? composer : null) };
    __out({ beside: at(1036, 882, null), onComposer: at(1012, 882, composer), nowhere: at(300, 300, null) });
    """)
    assert out == {"beside": "tray", "onComposer": "chat", "nowhere": None}


@needs_node
def test_hovering_the_button_springs_the_tray_open_and_it_stays_until_the_drop() -> None:
    out = run(FILES, STUBS + """
    const { button } = fakeTray();
    const timers = [];
    globalThis.setTimeout = (fn) => { timers.push(fn); return timers.length; };
    document.elementFromPoint = () => null;
    const g = { ref: objRef("note", 1, "One"), x: 1012, y: 882 };
    objCarryBegin(g);
    objTrayDoor.cue(g);                       // over the button: the timer starts
    const armed = timers.length;
    objTrayDoor.cue(g);                       // still over it: not a second timer
    const once = timers.length;
    timers[0]();                              // 400 ms later
    const opened = { clicks: button.clicks, expanded: button.expanded, flag: g.trayOpened };
    objCarryDrop({ ...g, x: 1012, y: 882 }); // dropped on the button
    __out({ armed, once, opened, afterDrop: { expanded: button.expanded, held: objTray.map(objKey) } });
    """)
    assert out["armed"] == 1 and out["once"] == 1
    assert out["opened"] == {"clicks": 1, "expanded": "true", "flag": True}
    assert out["afterDrop"] == {"expanded": "true", "held": ["note:1"]}


@needs_node
def test_a_tray_the_drag_opened_is_put_back_when_the_card_goes_elsewhere() -> None:
    out = run(FILES, STUBS + """
    const { button } = fakeTray();
    const timers = [];
    globalThis.setTimeout = (fn) => { timers.push(fn); return timers.length; };
    document.elementFromPoint = () => null;
    const g = { ref: objRef("note", 1, "One"), x: 1012, y: 882 };
    objCarryBegin(g);
    objTrayDoor.cue(g); timers[0]();
    const opened = button.expanded;
    g.x = 100; g.y = 100;                    // the card is taken away and dropped on nothing
    objCarryDrop(g);
    const afterElsewhere = { expanded: button.expanded, held: objTray.length };
    // a tray the hand opened is left alone by a drag that never sprang it
    button.click();
    const h = { ref: objRef("note", 2, "Two"), x: 100, y: 100 };
    objCarryBegin(h); objCarryDrop(h);
    __out({ opened, afterElsewhere, handOpened: button.expanded });
    """)
    assert out == {"opened": "true", "afterElsewhere": {"expanded": "false", "held": 0}, "handOpened": "true"}


@needs_node
def test_leaving_the_button_before_the_spring_cancels_it() -> None:
    out = run(FILES, STUBS + """
    const { button } = fakeTray();
    const timers = []; const cleared = [];
    globalThis.setTimeout = (fn) => { timers.push(fn); return timers.length; };
    globalThis.clearTimeout = (id) => cleared.push(id);
    const g = { ref: objRef("note", 1, "One"), x: 1012, y: 882 };
    objCarryBegin(g);
    objTrayDoor.cue(g);
    g.x = 100; g.y = 100;
    objTrayDoor.cue(g);
    __out({ timers: timers.length, cleared, timerNow: g.trayTimer, clicks: button.clicks });
    """)
    assert out == {"timers": 1, "cleared": [1], "timerNow": 0, "clicks": 0}


@needs_node
def test_every_kind_of_object_lands_in_the_tray() -> None:
    out = run(FILES, STUBS + """
    fakeTray();
    document.elementFromPoint = () => null;
    const landed = {};
    for (const kind of OBJ_KINDS) {
      const ref = objRef(kind, 3, `A ${kind}`, kind === "image" || kind === "file" ? "/media/x" : "");
      objTray = [];
      objCarryDrop({ ref, x: 1012, y: 882 });
      landed[kind] = objTray.map(objKey);
    }
    __out(landed);
    """)
    #: Diagram joined the object kinds with the diagram builder (R7), upload with chat attach (INBOX 1687);
    #: every kind lands, so it is listed.
    assert out == {kind: [f"{kind}:3"] for kind in ["note", "document", "board", "map", "diagram", "image", "file", "upload"]}


@needs_node
def test_a_chat_source_card_is_a_button_that_still_takes_a_drag() -> None:
    out = run(FILES, STUBS + """
    fakeTray();
    const card = { dataset: { obj: "document:9", objTitle: "Quarterly plan" }, matches: (sel) => sel === "[data-obj]" };
    const control = { matches: (sel) => sel.includes(".chat-source-card[data-obj]") };
    const target = { closest: (sel) => (sel === OBJ_NO_GRAB ? control : sel === OBJ_CARD_SELECTOR ? card : null), tagName: "SPAN" };
    card.closest = (sel) => (sel === OBJ_CARD_SELECTOR ? card : null);
    const seed = objDragSeed({ button: 0, defaultPrevented: false, target, pointerType: "mouse" });
    const plain = { matches: () => false };
    const stray = { closest: (sel) => (sel === OBJ_NO_GRAB ? plain : sel === OBJ_CARD_SELECTOR ? card : null), tagName: "SPAN" };
    __out({ ref: seed?.ref && objKey(seed.ref), mode: seed?.mode, title: seed?.ref?.title, refusedPlainButton: objDragSeed({ button: 0, defaultPrevented: false, target: stray, pointerType: "mouse" }) });
    """)
    assert out == {"ref": "document:9", "mode": "carry", "title": "Quarterly plan", "refusedPlainButton": None}


def test_the_chat_source_card_carries_its_reference_and_the_drag_lists_it() -> None:
    kit = (JS / "answer-kit.js").read_text(encoding="utf-8")
    assert 'card.dataset.obj = `${source.kind}:${source.id}`' in kit
    assert '["note", "document", "board", "map"].includes(source.kind)' in kit
    drag = (JS / "obj-drag.js").read_text(encoding="utf-8")
    assert '.obj-tray-use, .chat-source-card[data-obj]' in drag
    assert 'dragFlag.hold("obj")' in drag, "every live drag sets the shared flag"
    assert re.search(r"try \{\s*OBJ_MODES\[g\.mode\]\[cancel \? \"cancel\" : \"drop\"\]\(g, event\);\s*\} finally \{\s*dragFlag\.release", drag), \
        "a drop that throws must still release the flag"


def test_the_drag_state_is_read_by_the_closers_and_nothing_else_keeps_its_own_flag() -> None:
    assert MENUS.count("dragFlag.active()") >= 3, "outside click, popover scroll and menu scroll all ask"
    other = [p.name for p in JS.glob("*.js") if p.name != "menus.js" and re.search(r"\bconst dragFlag\b|new Set\(\);\s*let endedAt", p.read_text(encoding="utf-8"))]
    assert other == []


@pytest.mark.parametrize("name", ["obj-carry.js", "obj-tray.js", "menus.js", "obj-drag.js"])
def test_the_scripts_still_parse(name: str) -> None:
    import shutil

    if not shutil.which("node"):
        pytest.skip("needs node")
    proc = subprocess.run(["node", "--check", str(Path(JS / name))], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
