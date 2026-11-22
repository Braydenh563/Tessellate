"""Rows not built fold into one spacer per fifty (L-world-class-873).

A Notes switch at 4,628 notes styled and laid out 4,380 one-element shells
every time the tab showed (74 to 100ms of style recalc). `windowRows` with
`o.run` lands unbuilt rows as `row-run` spacers as tall as the shells they
stand for; a run near the window opens, far shells fold back once the scroll
settles, and a lookup by key goes through `rowFor`. Runs under node against
the fake DOM of tests/test_window_rows.py, with a fixed clock. Measured in the
app: the switch median went from 142ms to 70ms (CHANGELOG).
"""

from __future__ import annotations

from tests._app_js import frontend_text
from tests.test_window_rows import _run, pytestmark  # noqa: F401  (needs node)

PATCH = """
El.prototype.replaceWith = function (...next) { const k = this.parent.kids; k.splice(k.indexOf(this), 1, ...next); next.forEach((n) => { n.parent = this.parent; }); this.parent = null; };
El.prototype.before = function (...next) { const k = this.parent.kids; k.splice(k.indexOf(this), 0, ...next); next.forEach((n) => { n.parent = this.parent; }); };
El.prototype.remove = function () { const k = this.parent.kids; k.splice(k.indexOf(this), 1); this.parent = null; };
El.prototype.append = function (...n) { n.forEach((x) => this.appendChild(x)); };
Object.defineProperty(El.prototype, 'children', { get() { return this.kids; } });
IntersectionObserver.prototype.unobserve = function (el) { this.seen.delete(el); };
const runs = (list) => list.kids.filter((k) => k.classList.contains('row-run'));
const count = (list) => list.kids.reduce((n, k) => n + (k.classList.contains('row-run') ? Number(k.dataset.run) : 1), 0);
"""


def test_unbuilt_rows_land_as_runs_of_fifty_as_tall_as_their_shells():
    out = _run(PATCH + """
const { items, list, win } = make(5000, { run: 50, gap: '8px' });
win.add(list, items, (item, i) => i < 12);
const r = runs(list);
process.stdout.write(JSON.stringify({ kids: list.kids.length, runs: r.length, count: count(list), built: built.length,
  first: String(r[0].dataset.run), css: r[0].style.cssText, keyed: r[0].dataset.id ?? null, hidden: r[0].attrs['aria-hidden'],
  keys: win.keys(list).length, lastKey: win.keys(list)[4999] }));
""")
    assert out["kids"] == 12 + 100 and out["runs"] == 100 and out["count"] == 5000 and out["built"] == 12
    assert out["first"] == "50" and "height:calc(2500px + 49 * 8px)" in out["css"] and "visibility:hidden" in out["css"]
    assert out["keyed"] is None and out["hidden"] == "true"
    assert out["keys"] == 5000 and out["lastKey"] == 5000


def test_a_lookup_by_key_opens_only_the_run_that_holds_it():
    out = _run(PATCH + """
const { items, list, win } = make(500, { run: 50 });
win.add(list, items, (item, i) => i < 2);
const before = list.kids.length;
const row = win.rowFor(300);
process.stdout.write(JSON.stringify({ before, after: list.kids.length, id: row.dataset.id, shell: row.classList.contains('row-shell'),
  run: row.classList.contains('row-run'), count: count(list), missing: win.rowFor(9999) }));
""")
    assert out["after"] == out["before"] + 49 and out["count"] == 500
    assert out["id"] == "300" and out["shell"] and not out["run"] and out["missing"] is None


def test_a_run_near_the_window_opens_and_its_shells_are_then_built():
    out = _run(PATCH + """
const { items, list, win } = make(200, { run: 50 });
win.add(list, items, (item, i) => i < 2);
const run = list.kids[2];
io.cb([{ target: run, isIntersecting: true, boundingClientRect: { top: 500, height: 2500 }, rootBounds: { top: 0 } }]);
const opened = list.kids.length;
io.cb([{ target: list.kids[2], isIntersecting: true, boundingClientRect: { top: 500, height: 50 }, rootBounds: { top: 0 } }]);
process.stdout.write(JSON.stringify({ opened, watched: io.seen.has(run), built: built.slice() }));
""")
    assert out["opened"] == 2 + 50 + 3 and out["watched"] is False
    assert out["built"] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_the_keyboard_coming_up_into_a_run_builds_its_last_row():
    out = _run(PATCH + """
const { items, list, win } = make(120, { run: 50 });
win.add(list, items, (item, i) => i < 2);
const down = win.fill(list.kids[2]);
const up = win.fill(list.kids[list.kids.length - 1], true);
process.stdout.write(JSON.stringify({ down: down.dataset.id, up: up.dataset.id, shells: [down, up].map((r) => r.classList.contains('row-shell')) }));
""")
    assert out["down"] == "3" and out["up"] == "120" and out["shells"] == [False, False]


def test_far_shells_fold_back_into_runs_once_the_scroll_settles():
    out = _run(PATCH + """
const { items, list, win } = make(300, { run: 50 });
root.appendChild(list); // a list that left the page is not folded
win.add(list, items, (item, i) => i < 2);
win.rowFor(100); win.rowFor(160);
const opened = list.kids.length;
list.kids.forEach((k, i) => { k.top = i < 2 ? 0 : 20000; });
list.kids[60].tabIndex = 0; // the one Tab stop is never folded
io.cb([]);
timers.forEach((fn) => fn());
process.stdout.write(JSON.stringify({ opened, kids: list.kids.length, count: count(list), stop: list.kids.some((k) => k.tabIndex === 0 && !k.classList.contains('row-run')),
  order: win.keys(list).slice(0, 3) }));
""")
    assert out["opened"] > 100 and out["kids"] < 15 and out["count"] == 300 and out["stop"]
    assert out["order"] == [1, 2, 3]


def test_every_notes_lookup_by_id_goes_through_note_row_for():
    """A query alone misses a row folded into a run, so no file asks the list for one."""
    import re

    from tests._app_js import JS_DIR

    pattern = re.compile(r"querySelector\(`#entry-list >? ?li\[data-id=\"\$\{")
    found = [p.name for p in sorted(JS_DIR.glob("*.js")) if pattern.search(p.read_text(encoding="utf-8"))]
    assert found == [], found
    notes = frontend_text("notes-list.js")
    assert "function noteRowFor(id)" in notes and "noteWindow.win.rowFor(Number(id))" in notes
    assert "run: NOTE_WINDOW.run" in notes
