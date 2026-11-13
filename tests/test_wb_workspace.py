"""L-whiteboard-7 (edit inside a group, the rest dimmed) and L-whiteboard-8 (saved board workspaces).
whiteboard-workspace.js runs in node against a stand-in for the page and the board's functions."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text

INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

SCRIPT = """
const log = { said: [], toasts: [], clicks: [], opened: [], closed: 0, formatToggles: 0 };
const classes = {};
const mkEl = (id, hidden) => { const el = { id, hidden, classList: {
  contains: (c) => (c === "hidden" ? el.hidden : Boolean((classes[id] || new Set()).has(c))),
  toggle: (c, on) => { (classes[id] ||= new Set())[on ? "add" : "delete"](c); },
}, click() { log.clicks.push(id); el.hidden = !el.hidden; }, dispatchEvent() { log.clicks.push(id + ":change"); } }; return el; };
const els = { "library-view-whiteboard": mkEl("library-view-whiteboard", false), "wb-navigator": mkEl("wb-navigator", true),
  "wb-search-bar": mkEl("wb-search-bar", false), "wb-format": mkEl("wb-format", true), "wb-sidebar-panel": mkEl("wb-sidebar-panel", false),
  "wb-panel-props": Object.assign(mkEl("wb-panel-props", false), { checked: true }) };
const items = %(items)s;
const itemEls = {};
const document = { activeElement: %(active)s,
  getElementById: (id) => els[id] || null,
  querySelector: (sel) => { const m = /data-id="(\\d+)"/.exec(sel); const key = sel.split("[")[0] + m[1]; return itemEls[key] ||= mkEl(key, false); } };
const WB_LIST_BY_KIND = { sketch: "sketches", node: "nodes", object: "objects" };
const WB_SELECTOR_BY_KIND = { sketch: (id) => `.s[data-id="${id}"]`, node: (id) => `.n[data-id="${id}"]`, object: (id) => `.o[data-id="${id}"]` };
const wbState = { sketches: items, nodes: [], objects: [] };
const wbIsLinkSketch = (s) => /"type"\\s*:\\s*"link-/.test(s.data || "");
const wbSketchData = (s) => JSON.parse(s.data);
const wbFindItem = (kind, id) => (kind === "sketch" ? items : []).find((i) => i.id === id) || null;
const wbGroupChain = (item) => (item.group_id ? String(item.group_id).split(">") : []);
const wbItemsWithGroupPrefix = (p) => items.filter((i) => p.every((s, n) => wbGroupChain(i)[n] === s)).map((item) => ({ kind: "sketch", item }));
const wbCommonGroupPrefix = (list) => { const c = list.map(wbGroupChain); const out = []; for (let i = 0; i < c[0].length; i++) { if (!c.every((x) => x[i] === c[0][i])) break; out.push(c[0][i]); } return out; };
let selection = %(selection)s;
const wbFmtEntries = () => items.filter((i) => selection.includes(i.id)).map((item) => ({ kind: "sketch", item }));
const wbAnnounce = (t) => log.said.push(t);
const toast = (t) => log.toasts.push(t);
const handlers = {};
const window = { addEventListener: (t, fn, cap) => (handlers[t] = { fn, cap }) };
const mem = %(store)s;
const prefs = { json: (k, d) => (mem[k] ? JSON.parse(mem[k]) : d), set: (k, v) => (mem[k] = v) };
let sideTab = "layers";
const wbSideState = () => ({ tab: sideTab });
const wbOpenSidebar = (tab) => { log.opened.push(tab); els["wb-sidebar-panel"].hidden = false; };
const wbCloseSidebar = () => { log.closed += 1; els["wb-sidebar-panel"].hidden = true; };
const wbToggleNavigator = () => { log.clicks.push("navigator"); els["wb-navigator"].hidden = !els["wb-navigator"].hidden; };
const wbOpenBoardSearch = () => { log.clicks.push("search"); els["wb-search-bar"].hidden = false; };
const wbCloseBoardSearch = () => { log.clicks.push("search"); els["wb-search-bar"].hidden = true; };
const wbFormatToggle = () => { log.formatToggles += 1; els["wb-format"].hidden = !els["wb-format"].hidden; };
const promptDialog = async () => %(prompt)s;
const onSurface = () => {};
const wbFmtState = {};
%(src)s
const dimmed = () => Object.entries(itemEls).filter(([, e]) => classes[e.id]?.has("wb-dimmed")).map(([k]) => k).sort();
(async () => {
  %(body)s
})();
"""

ITEMS = [
    {"id": 1, "group_id": "a>b"}, {"id": 2, "group_id": "a>b"}, {"id": 3, "group_id": "a"}, {"id": 4, "group_id": None},
]


def _run(body: str, *, selection=None, active="null", store=None, prompt="null") -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = SCRIPT % {
        "items": json.dumps(ITEMS), "selection": json.dumps(selection or []), "active": active, "store": json.dumps(store or {}),
        "prompt": prompt, "src": frontend_text("whiteboard-workspace.js"), "body": body,
    }
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


EMIT = "console.log(JSON.stringify({ ...log, dimmed: dimmed(), store: mem, cls: Object.fromEntries(Object.entries(classes).map(([k, v]) => [k, [...v]])) }));"


def test_entering_a_group_dims_everything_outside_it_and_leaving_clears_it():
    got = _run('wbFmtState.isolate.enter(["a", "b"]); const mid = dimmed(); wbFmtState.isolate.leave(); '
               'console.log(JSON.stringify({ mid, after: dimmed(), out: wbFmtState.isolate.outside("sketch", {id: 3, group_id: "a"}) }));')
    assert got["mid"] == [".s3", ".s4"] and got["after"] == [] and got["out"] is False


def test_only_members_are_in_reach_while_inside():
    got = _run('wbFmtState.isolate.enter(["a"]); console.log(JSON.stringify([1, 2, 3, 4].map((id) => wbFmtState.isolate.outside("sketch", items.find((i) => i.id === id)))));')
    assert got == [False, False, False, True]


def test_escape_leaves_but_not_from_a_field_and_the_listener_is_capturing():
    leave = ('wbFmtState.isolate.enter(["a"]); const e = { key: "Escape", target: { closest: () => null }, preventDefault() {}, stopImmediatePropagation() { this.halted = 1; } };'
             'handlers.keydown.fn(e); console.log(JSON.stringify({ open: wbFmtState.isolate.active(), halted: Boolean(e.halted), cap: handlers.keydown.cap }));')
    assert _run(leave) == {"open": False, "halted": True, "cap": True}
    kept = _run(leave, active='{ tagName: "INPUT" }')
    assert kept["open"] is True and kept["halted"] is False


def test_the_selection_command_opens_the_innermost_shared_group_or_says_so():
    got = _run('console.log(JSON.stringify({ ok: wbFmtState.isolate.enterSelection(), depth: wbFmtState.isolate.depth() }));', selection=[1, 2])
    assert got == {"ok": True, "depth": 2}
    none = _run('console.log(JSON.stringify({ ok: wbFmtState.isolate.enterSelection(), t: log.toasts }));', selection=[4])
    assert none["ok"] is False and none["t"] == ["Select a grouped item first."]


def test_a_group_with_no_members_left_is_left_on_the_next_paint():
    got = _run('wbFmtState.isolate.enter(["a"]); items.length = 0; wbFmtState.isolate.paint(); console.log(JSON.stringify(wbFmtState.isolate.active()));')
    assert got is False


def test_a_snapshot_names_the_open_panels_and_the_sidebar_tab():
    got = _run("console.log(JSON.stringify(wbFmtState.workspaces.snapshot()));")
    assert got == {"props": True, "overview": False, "search": True, "format": False, "side": "layers"}


def test_saving_names_the_panels_and_switching_presses_only_what_differs():
    body = ('await wbFmtState.workspaces.save("Draw"); '
            'els["wb-navigator"].hidden = false; els["wb-search-bar"].hidden = true; els["wb-format"].hidden = false; els["wb-sidebar-panel"].hidden = true; '
            "wbFmtState.workspaces.use('Draw'); " + EMIT)
    got = _run(body)
    assert json.loads(got["store"]["wb-workspaces"]) == [{"name": "Draw", "panels": {"props": True, "overview": False, "search": True, "format": False, "side": "layers"}}]
    assert got["clicks"] == ["navigator", "search"] and got["formatToggles"] == 1 and got["opened"] == ["layers"]


def test_a_workspace_saved_under_a_name_in_use_is_replaced_and_the_list_is_capped():
    body = ('for (let i = 0; i < 9; i++) await wbFmtState.workspaces.save("W" + i); await wbFmtState.workspaces.save("W0"); '
            "console.log(JSON.stringify({ names: wbFmtState.workspaces.saved().map((w) => w.name), t: log.toasts }));")
    got = _run(body)
    assert len(got["names"]) == 8 and got["names"][-1] == "W0" and got["t"][0].startswith("Keep at most 8")


def test_the_save_prompt_name_is_trimmed_and_an_empty_one_saves_nothing():
    assert _run('console.log(JSON.stringify(await wbFmtState.workspaces.save()));', prompt='"   "') is False
    got = _run("await wbFmtState.workspaces.save(); " + EMIT, prompt='"  Review  "')
    assert json.loads(got["store"]["wb-workspaces"])[0]["name"] == "Review"


def test_the_menu_rows_switch_save_and_delete():
    store = {"wb-workspaces": json.dumps([{"name": "Draw", "panels": {}}])}
    got = _run("console.log(JSON.stringify(wbFmtState.workspaces.rows().map((r) => [r.label, r.group || '', Boolean(r.danger)])));", store=store)
    assert got == [["ph:layout Draw", "", False], ["ph:floppy-disk Save the open panels as a workspace…", "manage", False], ["ph:trash Delete Draw", "manage", True]]


def test_the_wiring_is_in_the_source():
    src = script_file_text("whiteboard-workspace.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()
    board = script_file_text("whiteboard.js")
    for needle in ("wbFmtState.isolate?.depth()", "wbFmtState.isolate?.enter(chain.slice(0, depth))", "wbFmtState.isolate?.paint()", "!wbFmtState.isolate?.outside(kind, item)"):
        assert needle in board, needle
    assert board.count('wbFmtState.isolate?.outside("node", node)') == 2 and board.count('wbFmtState.isolate?.outside("sketch", sketch)') == 2
    cmds = script_file_text("whiteboard-commands.js")
    for ident in ("enter-group", "leave-group", "save-workspace"):
        assert f'id: "{ident}"' in cmds
    assert "/js/whiteboard-workspace.js" in frontend_text("lazy-entries.js")
    assert 'id="wb-workspaces"' in INDEX.read_text(encoding="utf-8")
    css = (INDEX.parent / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".wb-dimmed" in css and "pointer-events: none" in css.split(".wb-dimmed")[1].split("}")[0]


def _link(id, source, target, **extra):
    data = {"type": "link-straight", "sourceKind": "sketch", "targetKind": "sketch", "sourceId": source, "targetId": target, **extra}
    return {"id": id, "group_id": None, "data": json.dumps(data)}


def test_a_connector_between_two_members_stays_undimmed_and_in_reach_inside_a_group():
    #: L-whiteboard-19: items 1 and 2 are in group a>b; a link joining them is not dimmed, one to item 4 (outside) or with a free end is.
    links = [_link(5, 1, 2), _link(6, 1, 4), _link(7, 1, None)]
    got = _run(
        f"items.push(...{json.dumps(links)}); wbFmtState.isolate.enter(['a', 'b']);"
        "console.log(JSON.stringify({ dimmed: dimmed(), out: [5, 6, 7].map((id) => wbFmtState.isolate.outside('sketch', items.find((i) => i.id === id))) }));"
    )
    assert got["dimmed"] == [".s3", ".s4", ".s6", ".s7"]
    assert got["out"] == [False, True, True]


def test_find_and_overview_are_only_view_switches_now_l265():
    html = INDEX.read_text(encoding="utf-8")
    assert "wb-search-toggle" not in html and "wb-navigator-toggle" not in html
    assert 'id="wb-panel-search"' in html and 'id="wb-panel-overview"' in html
