"""A board edited in place in a document (L-documents-104), against a stub instance API.

The whiteboard's per-instance API (PR 223) is not built yet, so `window.wbInstance.create` here is a stub that counts what it
is given; the page was not driven. documents-board.js runs in node over a small fake DOM.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

_HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(%(path)s, "utf8");
class Node_ {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.dataset = {}; this.kids = []; this.parent = null; this.cls = new Set(); this.ls = {}; this.focused = 0; }
  get isConnected() { let n = this; while (n.parent) n = n.parent; return n === DOC.body; }
  get classList() { const c = this.cls; return { add: (x) => c.add(x), remove: (x) => c.delete(x), contains: (x) => c.has(x), toggle: () => {} }; }
  set className(v) { this.cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
  get nextElementSibling() { const k = this.parent?.kids; return k ? k[k.indexOf(this) + 1] || null : null; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  removeAttribute(k) { delete this.attrs[k]; }
  append(...n) { for (const x of n) { x.remove?.(); x.parent = this; this.kids.push(x); } }
  after(n) { n.remove(); const i = this.parent.kids.indexOf(this); n.parent = this.parent; this.parent.kids.splice(i + 1, 0, n); }
  remove() { if (this.parent) this.parent.kids.splice(this.parent.kids.indexOf(this), 1); this.parent = null; }
  focus() { DOC.focused = this; }
  addEventListener(t, f) { (this.ls[t] ||= []).push(f); }
  removeEventListener(t, f) { this.ls[t] = (this.ls[t] || []).filter((x) => x !== f); }
  count() { return Object.values(this.ls).reduce((a, b) => a + b.length, 0); }
  fire(t, ev = {}) {  // bubbling: target, then parents, then document
    const e = { type: t, target: this, defaultPrevented: false, stopped: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this.stopped = true; }, ...ev };
    for (let n = this; n && !e.stopped; n = n.parent) for (const f of [...(n.ls[t] || [])]) f(e);
    if (!e.stopped) for (const f of [...(DOC.ls[t] || [])]) f(e);
    return e;
  }
  all(list = []) { for (const k of this.kids) { list.push(k); k.all(list); } return list; }
}
const DOC = new Node_("document");
DOC.body = new Node_("body"); DOC.body.parent = null;
DOC.createElement = (t) => new Node_(t);
DOC.createElementNS = (_n, t) => new Node_(t);
DOC.getElementById = () => null;
DOC.documentElement = DOC.body;
DOC.querySelectorAll = (sel) => {
  const m = /^\.([\w-]+)\[data-board-id="(\d+)"\]$/.exec(sel);
  return m ? DOC.body.all().filter((n) => n.cls.has(m[1]) && n.dataset.boardId === m[2]) : [];
};
DOC.querySelector = () => null;
Object.defineProperty(DOC, "isConnected", { value: true });
const WIN = new Node_("window");
const toasts = [];
const made = [];
let changeFns = [];
WIN.wbInstance = %(api)s ? { create: async (host, id, opts) => {
  const rec = { host, id, opts, destroyed: 0, focused: 0, change: null, reloaded: 0 };
  made.push(rec);
  return { destroy() { rec.destroyed++; }, focus() { rec.focused++; }, onChange(fn) { rec.change = fn; return () => { rec.change = null; }; }, reload: %(reload)s ? () => { rec.reloaded++; } : undefined };
} } : undefined;
const G = { document: DOC, window: WIN, toast: (m) => toasts.push(m), voiceLine: (k) => k,
  smallButton: () => new Node_("button"), ensureModule: async () => true, lazyScript() {}, lazyLoadFailed() {}, apiJson: async () => ({}),
  dialogHead: () => new Node_("div"), activeOverlay: () => null, nounCount: () => "", diagramModel: { view: { wire() {} } },
  CustomEvent: class { constructor(t, o) { this.type = t; Object.assign(this, o); } }, Event: class { constructor(t) { this.type = t; } }, setTimeout };
WIN.dispatchEvent = () => {}; WIN.addEventListener = Node_.prototype.addEventListener; WIN.removeEventListener = Node_.prototype.removeEventListener;
new Function(...Object.keys(G), src)(...Object.values(G));
const card = (id) => { const b = new Node_("button"); b.className = "doc-embed-board-live"; b.dataset.boardId = String(id); DOC.body.append(b); return b; };
const press = (b) => b.fire("board-live", { detail: { id: Number(b.dataset.boardId) } });
const tick = () => new Promise((r) => setTimeout(r, 5));
const mutate = () => [...(DOC.ls["doc-saved"] || [])].forEach((f) => f({}));
const watchers = () => (DOC.ls["doc-saved"] || []).length + (DOC.ls["doc-shown"] || []).length;
const out = {};
(async () => {
  %(body)s
  console.log(JSON.stringify(out));
})();
"""


def _run(body: str, api: bool = True, reload: bool = True) -> dict:
    path = ROOT / "frontend/js/documents-board.js"
    src = _HARNESS % {"path": json.dumps(str(path)), "api": json.dumps(api), "reload": json.dumps(reload), "body": body}
    done = subprocess.run(["node", "-"], input=src, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_two_cards_get_one_editable_instance_each_and_destroy_clears_everything():
    r = _run("""
      const a = card(1), b = card(1);
      const base = WIN.ls.pagehide?.length || 0;
      press(a); press(b); await tick();
      out.made = made.length; out.editable = made.every((m) => m.opts.editable === true);
      out.pressed = [a.attrs["aria-pressed"], b.attrs["aria-pressed"]];
      out.observers = watchers();
      out.hostListeners = made.map((m) => m.host.count() > 0);
      press(a); await tick();
      out.afterOne = [made[0].destroyed, made[1].destroyed, a.attrs["aria-pressed"]];
      b.remove(); made[1].host.remove(); mutate(); await tick();
      out.afterRemoval = [made[1].destroyed, WIN.ls.pagehide?.length || 0, base, watchers()];
      out.hostLeft = [made[0].host.count(), made[1].host.count(), made[0].host.isConnected, made[1].host.isConnected];
      out.rec = made.map((m) => m.change === null);
    """)
    assert r["made"] == 2 and r["editable"] is True
    assert r["pressed"] == ["true", "true"] and r["observers"] == 2
    assert all(r["hostListeners"])
    assert r["afterOne"] == [1, 0, "false"]
    # a card removed from the page takes its instance; the last one takes the observer and the pagehide listener
    assert r["afterRemoval"] == [1, 0, 0, 0]
    assert r["hostLeft"] == [0, 0, False, False]
    assert r["rec"] == [True, True]


def test_a_card_that_comes_back_after_a_redraw_keeps_its_instance():
    r = _run("""
      const a = card(2); press(a); await tick();
      a.remove(); made[0].host.remove(); const again = card(2);   // the document redrew its cards
      mutate(); await tick();
      out.kept = made[0].destroyed; out.host = made[0].host.parent === again.parent && again.nextElementSibling === made[0].host;
    """)
    assert r["kept"] == 0 and r["host"] is True


def test_the_document_closing_destroys_every_instance():
    r = _run("""
      press(card(3)); press(card(4)); await tick();
      WIN.fire("pagehide");
      out.d = made.map((m) => m.destroyed);
    """)
    assert r["d"] == [1, 1]


def test_escape_returns_the_focus_to_the_card_and_the_boards_own_escape_is_left_alone():
    r = _run("""
      const a = card(5); press(a); await tick();
      const host = made[0].host;
      const used = host.fire("keydown", { key: "Escape", defaultPrevented: true });
      out.used = DOC.focused === a;
      const free = host.fire("keydown", { key: "Escape" });
      out.free = [DOC.focused === a, free.defaultPrevented];
    """)
    assert r["used"] is False
    assert r["free"] == [True, True]


def test_typing_in_a_board_never_reaches_the_documents_undo():
    r = _run("""
      let seen = 0;
      for (const t of ["keydown", "beforeinput", "input", "paste"]) DOC.addEventListener(t, () => seen++);
      const a = card(6); press(a); await tick();
      const host = made[0].host;
      for (const t of ["keydown", "beforeinput", "input", "paste"]) host.fire(t, { key: "z", ctrlKey: true });
      out.seen = seen;
    """)
    assert r["seen"] == 0


def test_two_cards_of_one_board_follow_each_others_edits_and_another_board_is_left():
    r = _run("""
      const a = card(7), b = card(7), c = card(8);
      press(a); press(b); press(c); await tick();
      made[0].change();
      out.reload = made.map((m) => m.reloaded);
    """)
    assert r["reload"] == [0, 1, 0]


def test_without_reload_a_sibling_is_made_again():
    r = _run("""
      const a = card(9), b = card(9); press(a); press(b); await tick();
      made[0].change(); await tick();
      out.made = made.length; out.old = made[1].destroyed; out.edits = made[0].destroyed;
    """, reload=False)
    assert r["made"] == 3 and r["old"] == 1 and r["edits"] == 0


def test_without_the_api_show_live_stays_the_read_only_window():
    r = _run("""
      const a = card(10); press(a); await tick();
      out.made = made.length; out.observers = watchers();
      out.window = a.nextElementSibling?.cls.has("doc-board-live") === true;
      out.pressed = a.attrs["aria-pressed"];
      press(a); out.closed = a.attrs["aria-pressed"];
    """, api=False)
    assert r["made"] == 0 and r["observers"] == 0
    assert r["window"] is True and r["pressed"] == "true" and r["closed"] == "false"


def test_a_failing_instance_says_so_and_leaves_no_window():
    r = _run("""
      WIN.wbInstance.create = async () => { throw new Error("no board"); };
      const a = card(11); press(a); await tick();
      out.toast = toasts.length; out.window = a.nextElementSibling === null; out.pressed = a.attrs["aria-pressed"];
      out.observers = watchers();
    """)
    assert r["toast"] == 1 and r["window"] is True and r["pressed"] == "false" and r["observers"] == 0


def test_a_card_pressed_off_while_the_instance_is_still_being_made_destroys_it_when_it_arrives():
    r = _run("""
      let release;
      WIN.wbInstance.create = (host) => new Promise((res) => { release = () => res({ destroy() { out.destroyed = (out.destroyed || 0) + 1; }, onChange() { return () => {}; } }); });
      const a = card(12); press(a); await tick();
      press(a); release(); await tick();
      out.destroyed = out.destroyed; out.pressed = a.attrs["aria-pressed"];
    """)
    assert r["destroyed"] == 1 and r["pressed"] == "false"
