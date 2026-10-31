"""perf-1031 leftovers (perf3-1031): a page that arrives adds its rows, and
the numbers that did not move are not recomputed or redrawn.
Each test names the cost it keeps out; the figures are in CHANGELOG.md."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import JS_DIR, frontend_text

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _body(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


GROWN = r"""
const notesViewMode = "cards";
const list = { childElementCount: 0, lastElementChild: null };
const noteWindow = { win: {}, list, mode: "cards", items: null };
%(source)s
const note = (id) => ({ id });
const pair = (id, depth = 0) => [note(id), depth];
function shown(items) {
  noteWindow.items = items;
  list.childElementCount = items.length;
  list.lastElementChild = { dataset: { id: String(items[items.length - 1][0].id) } };
}
const out = {};
%(probes)s
console.log(JSON.stringify(out));
"""


def _grown(probes: str) -> dict:
    source = (JS_DIR / "notes-list.js").read_text(encoding="utf-8")
    match = re.search(r"^function noteListGrownBy\(.*?^\}\n", source, re.S | re.M)
    assert match
    script = GROWN % {"source": match.group(0), "probes": probes}
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(done.stdout)


@needs_node
def test_rows_that_extend_the_drawn_ones_are_the_only_ones_added():
    out = _grown(
        """
const a = pair(1), b = pair(2), c = pair(3), d = pair(4);
shown([a, b]);
out.tail = noteListGrownBy(list, [a, b, c, d]).map((p) => p[0].id);
"""
    )
    assert out["tail"] == [3, 4]


@needs_node
def test_anything_but_a_pure_extension_redraws_the_list():
    out = _grown(
        """
const a = pair(1), b = pair(2), c = pair(3);
shown([a, b]);
out.same = noteListGrownBy(list, [a, b]);                    // nothing new: a note changed in place
out.replaced = noteListGrownBy(list, [a, pair(2), c]);        // same id, a new object
out.moved = noteListGrownBy(list, [b, a, c]);                 // order moved
out.depth = noteListGrownBy(list, [a, [b[0], 1], c]);         // a thread joined
out.shrunk = noteListGrownBy(list, [a]);
list.childElementCount = 3;                                   // a skeleton or a held note in the list
out.foreign = noteListGrownBy(list, [a, b, c]);
list.childElementCount = 2;
list.lastElementChild = { dataset: {} };
out.skeleton = noteListGrownBy(list, [a, b, c]);
shown([a, b]);
noteWindow.mode = "rows";
out.mode = noteListGrownBy(list, [a, b, c]);
noteWindow.mode = "cards";
noteWindow.win = null;
out.stopped = noteListGrownBy(list, [a, b, c]);
noteWindow.win = {};
noteWindow.items = null;
out.fresh = noteListGrownBy(list, [a, b, c]);
"""
    )
    assert all(value is None for value in out.values()), out


def test_the_window_takes_new_rows_and_keeps_its_place():
    notes = frontend_text("notes-list.js")
    render = _body(notes, "function renderEntries(", "// --- note-list keyboard navigation")
    # The prefix check and the bail-out come before anything is cleared.
    assert render.index("const grown = noteListGrownBy(list, ordered);") < render.index("if (appendOnly && !grown) return;")
    assert render.index("if (appendOnly && !grown) return;") < render.index("const keep = grown ? null : resetNoteList(list);")
    assert "if (!grown && prefs.get(\"noteOutbox\", null)) renderPendingNoteRows();" in render
    windowed = _body(notes, "function renderWindowed(", "// BACKLOG §77 item 1")
    adds = _body(windowed, "if (grown) {", "noteWindow.win?.stop();")
    assert "noteWindow.win.add(list, grown);" in adds and "replaceChildren" not in adds


def test_a_page_in_a_long_list_appends_or_waits_for_the_last_page():
    notes = frontend_text("notes-list.js")
    schedule = _body(notes, "function scheduleEntriesProgress()", "async function loadEntries")
    assert 'allEntries.length <= ENTRIES_PROGRESS_LIST_MAX ? true : "append"' in schedule
    paint = _body(notes, "function paintEntriesProgress(", "function renderEntriesWhenShown")
    assert 'renderEntriesWhenShown(list === "append")' in paint
    gate = _body(notes, "function renderEntriesWhenShown(", "const ENTRIES_PROGRESS_LIST_MAX")
    assert "renderEntries(appendOnly)" in gate
