"""Move to bin from a note's menu keeps a keyboard user's place (sweep 1028b W8).

The row menu's "Move to bin" removed the card the focus sat in, so
`document.activeElement` fell to `body` and the next Tab started from the top of
the page. The Delete key on a row already handed the focus to the next row
(`initEntryListKeyboardNav`); the menu path did not. `binFocusHeir`
(frontend/js/note-cards.js) takes the neighbour before the delete and, once the
list is redrawn, focuses it only if the focus was lost; an emptied list lands on
the capture bar's field.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import app_js_text

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
%(source)s
const focused = [];
let active = null;
const body = { isConnected: true };
const make = (id) => ({ dataset: { id: String(id) }, tabIndex: -1, focus() { focused.push('row ' + id); active = this; } });
let rows = [];
const list = {
  querySelector(sel) {
    const m = /li\[data-id="(\d+)"\]/.exec(sel);
    return m ? rows.find((r) => r.dataset.id === m[1]) || null : null;
  },
};
const field = { focus() { focused.push('capture'); } };
const document = {
  body,
  get activeElement() { return active; },
  getElementById: (id) => (id === 'entry-list' ? list : id === 'capture-bar-input' ? field : null),
};
const entryListItems = () => rows;
// Reduced motion's 0s: the leaving row's fade (L462) plays nothing here.
const getComputedStyle = () => ({ getPropertyValue: () => '0s' });
const api = async () => {};
const pushUndo = () => ({});
const settleUndoFromToast = () => {};
const toastAction = () => {};
const toast = () => {};
const GO_TO_BIN = {};
const window = {};
let focusAfter = 'body';
async function refreshEntries() {
  rows = rows.filter((r) => r.dataset.id !== String(binned));
  active = focusAfter === 'body' ? body : focusAfter === 'other' ? { isConnected: true, id: 'other' } : active;
}
let binned = 0;
async function run(ids, id, after) {
  rows = ids.map(make);
  focused.length = 0;
  binned = id;
  focusAfter = after;
  active = rows.find((r) => r.dataset.id === String(id)) || body;
  await binNoteWithUndo({ id });
  return focused.slice();
}
(async () => {
  const out = {};
  %(probes)s
  process.stdout.write(JSON.stringify(out));
})();
"""


def _run(probes: str) -> dict:
    source = app_js_text()
    match = re.search(r"^async function binNoteWithUndo\(entry\) \{.*?^\}", source, re.S | re.M)
    assert match, "binNoteWithUndo is gone"
    script = HARNESS % {"source": match.group(0), "probes": probes}
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_the_next_row_takes_the_focus_when_it_was_lost():
    got = _run('out.mid = await run([1, 2, 3], 2, "body");')
    assert got["mid"] == ["row 3"]


def test_the_last_row_hands_it_to_the_one_before():
    got = _run('out.last = await run([1, 2, 3], 3, "body");')
    assert got["last"] == ["row 2"]


def test_focus_that_found_a_home_is_left_alone():
    got = _run('out.kept = await run([1, 2, 3], 2, "other");')
    assert got["kept"] == []


def test_an_emptied_list_lands_on_the_capture_field():
    got = _run('out.empty = await run([7], 7, "body");')
    assert got["empty"] == ["capture"]


def test_a_note_binned_from_elsewhere_moves_nothing():
    got = _run('out.away = await run([1, 2], 9, "body");')
    assert got["away"] == []
