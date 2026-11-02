"""One windowed list serves the Notes list and the Timeline feed (audit 1028 S16, S53).

`windowRows` (notes-list.js) holds every row as a one-element shell and builds
only the ones near the reader. These tests run it under node against a small
fake DOM, a fake `IntersectionObserver` and a fixed clock (timers are queued
and fired by the test, never waited for), so the rules are pinned without a
browser: how many rows are built, which ones come with a visible shell, which
are hollowed when the scroll settles, which are never hollowed, and that a
second `add` (a page of the Timeline) continues the first list's numbering.
The real thing, at 2,000 notes, is measured in the app (see CHANGELOG).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import JS_DIR

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
class El {
  constructor(tag) {
    this.tag = tag; this.dataset = {}; this.style = {}; this.attrs = {}; this.kids = []; this.parent = null;
    this.top = 0; this.height = 100; this.tabIndex = -1; this.cls = new Set();
    const cls = this.cls;
    this.classList = { add: (n) => cls.add(n), contains: (n) => cls.has(n) };
  }
  set className(v) { this.cls = new Set(v.split(' ').filter(Boolean)); const c = this.cls; this.classList = { add: (n) => c.add(n), contains: (n) => c.has(n) }; }
  setAttribute(k, v) { this.attrs[k] = v; }
  get parentElement() { return this.parent; }
  get isConnected() { return !!this.parent; }
  get nextElementSibling() { const k = this.parent.kids; return k[k.indexOf(this) + 1] || null; }
  get previousElementSibling() { const k = this.parent.kids; return k[k.indexOf(this) - 1] || null; }
  contains(el) { return el === this; }
  appendChild(node) { (node.frag ? node.kids : [node]).forEach((n) => { n.parent = this; this.kids.push(n); }); return node; }
  replaceWith(next) { const k = this.parent.kids; k[k.indexOf(this)] = next; next.parent = this.parent; this.parent = null; }
  getBoundingClientRect() { return { top: this.top, bottom: this.top + this.height, height: this.height }; }
}
const document = { activeElement: null, createElement: (t) => new El(t), createDocumentFragment: () => Object.assign(new El('frag'), { frag: true }) };
const innerHeight = 800;
const timers = [];
const setTimeout = (fn) => { timers.push(fn); return timers.length; };
const clearTimeout = () => {};
let io = null;
class IntersectionObserver {
  constructor(cb, opts) { this.cb = cb; this.opts = opts; this.seen = new Set(); io = this; }
  observe(el) { this.seen.add(el); }
  disconnect() { this.off = true; }
}
%(source)s
const heights = new Map();
const built = [];
const root = new El('div'); // the scroller: top 0, bottom 100 (height), moved by the test
root.height = 800;
function make(n, extra = {}) {
  const items = Array.from({ length: n }, (_, i) => ({ id: i + 1 }));
  const list = new El('ul');
  const win = windowRows(root, {
    heights, guess: 50, keyOf: (item) => item.id,
    tag: (li, item) => { li.dataset.id = String(item.id); },
    build: (item, i) => { built.push(item.id); const li = new El('li'); li.dataset.id = String(item.id); li.setAttribute('n', i); return li; },
    stays: (li) => li === document.activeElement,
    ...extra,
  });
  return { items, list, win };
}
const shells = (list) => list.kids.filter((k) => k.classList.contains('row-shell'));
%(probes)s
"""


def _run(probes: str) -> dict:
    source = (JS_DIR / "notes-list.js").read_text(encoding="utf-8")
    match = re.search(r"^const ROW_WINDOW_MARGIN.*?^function windowRows\(.*?^\}\n", source, re.S | re.M)
    assert match, "windowRows is gone from notes-list.js"
    script = HARNESS % {"source": match.group(0), "probes": probes}
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout)


def test_a_long_list_is_one_shell_per_row_and_only_the_first_screenful_is_built():
    out = _run("""
const { items, list, win } = make(5000);
win.add(list, items, (item, i) => i < 12);
process.stdout.write(JSON.stringify({
  rows: list.kids.length, shells: shells(list).length, built: built.length,
  shellHeight: shells(list)[0].style.cssText, hidden: shells(list)[0].attrs['aria-hidden'],
  keyed: shells(list)[0].dataset.id,
}));
""")
    assert out["rows"] == 5000 and out["built"] == 12 and out["shells"] == 4988
    assert "visibility:hidden" in out["shellHeight"] and "height:50px" in out["shellHeight"]
    assert out["hidden"] == "true" and out["keyed"] == "13"


def test_a_shell_that_comes_near_is_built_with_the_rows_beyond_it():
    out = _run("""
const { items, list, win } = make(100);
win.add(list, items, (item, i) => i < 2);
const target = list.kids[50];
io.cb([{ target, isIntersecting: true, boundingClientRect: { top: 500, height: 50 }, rootBounds: { top: 0 } }]);
const upTarget = list.kids[80];
io.cb([{ target: upTarget, isIntersecting: true, boundingClientRect: { top: -10, height: 50 }, rootBounds: { top: 0 } }]);
process.stdout.write(JSON.stringify({
  built: list.kids.map((k, i) => (k.classList.contains('row-shell') ? -1 : i)).filter((i) => i >= 0),
}));
""")
    # 0 and 1 from the start, 50..55 reading downwards, 75..80 reading upwards.
    assert out["built"] == [0, 1, 50, 51, 52, 53, 54, 55, 75, 76, 77, 78, 79, 80]


def test_a_row_far_from_the_window_is_hollowed_once_the_scroll_settles_and_keeps_its_height():
    out = _run("""
const { items, list, win } = make(60);
win.add(list, items, () => true);
list.kids.forEach((k, i) => { k.top = i * 100; k.height = 90 + (i % 2); });   // the window is 0..800
document.activeElement = list.kids[59];                                          // far, but holds focus
list.kids[58].tabIndex = 0;                                                      // far, but the one Tab stop
io.cb([]);                                                                       // a scroll event arms the settle timer
const before = list.kids.filter((k) => !k.classList.contains('row-shell')).length;
timers.splice(0).forEach((fn) => fn());
const after = list.kids.map((k, i) => (k.classList.contains('row-shell') ? -1 : i)).filter((i) => i >= 0);
process.stdout.write(JSON.stringify({
  before, after, height: heights.get(46), shellStyle: list.kids[45].style.cssText, hidden: list.kids[45].attrs['aria-hidden'],
}));
""")
    assert out["before"] == 60
    # Row i starts at i * 100; past 800 + 3000 is row 39 onwards. Rows 58 (Tab stop) and 59 (focus) stay.
    assert out["after"] == [*range(39), 58, 59]
    assert out["height"] == 91, "the drawn height is kept for the shell that replaces the row"
    assert "height:91px" in out["shellStyle"] and out["hidden"] == "true"


def test_a_second_add_continues_the_same_list_and_a_stopped_window_does_nothing():
    out = _run("""
const { items, list, win } = make(10);
win.add(list, items.slice(0, 6), (item, i) => i < 1);
win.add(list, items.slice(6), () => false);
const last = list.kids[9];
const filled = win.fill(last);
win.stop();
io.cb([{ target: list.kids[3], isIntersecting: true, boundingClientRect: { top: 1, height: 50 }, rootBounds: { top: 0 } }]);
process.stdout.write(JSON.stringify({
  rows: list.kids.length, filledId: filled.dataset.id, filledBuilt: !filled.classList.contains('row-shell'),
  numbered: filled.attrs.n, stillShell: list.kids[3].classList.contains('row-shell'), off: io.off,
}));
""")
    assert out["rows"] == 10 and out["filledId"] == "10" and out["filledBuilt"] is True
    assert out["numbered"] == 9, "the second add numbers its rows on from the first"
    assert out["stillShell"] is True and out["off"] is True
