"""The notes list's roving-focus keys leave a text field alone.

`initEntryListKeyboardNav` (frontend/js/notes-list.js) lets the arrow keys,
Home and End move between note rows. It listens on the whole list, and the
note's edit form is inside the list, so its title box, tags box and body editor
sent their Home, End and arrow keys to it as well: it called `preventDefault`
and moved the focus to another row. The caret never moved, and everything typed
afterwards went nowhere. Found by `scratchpad/ui-sweeps/deepflows.js`: click
into an open note's editor, press End, type, and the text is lost.
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
const calls = [];
const rows = [1, 2, 3].map((n) => ({
  dataset: { id: String(n) }, tabIndex: -1, focus() { calls.push('focus ' + n); },
  scrollIntoView() {},
}));
let handler = null;
const list = {
  addEventListener(type, fn) { if (type === 'keydown') handler = fn; },
  querySelectorAll() { return rows; },
};
const $ = () => list;
const entryListItems = (l) => l.querySelectorAll();
// The windowed list builds the row it moves to (`noteWindow.fill`); these rows are built.
const noteWindow = { fill: (li) => li };
const allEntries = [];
let editingId = null;
function openNoteEditor() { calls.push('edit'); }
function binNoteWithUndo() { calls.push('bin'); return Promise.resolve(); }
// The roving stop (UX-10, note-cards.js), its tab-index half: the controls
// half needs a DOM, and is measured by scratchpad/ui-sweeps/ux1005-tabstops.js
// (27 notes were 281 Tab stops; now the stop card's own, 5 to 7).
function entryListSetStop(items, stop) { items.forEach((li) => { li.tabIndex = li === stop ? 0 : -1; }); }
function entryListFocusStop() {}
initEntryListKeyboardNav();

// A node that answers `closest` for the simple selectors the handler uses:
// a part matches when it starts with one of the node's own tokens.
function press(key, tokens, { onRow = false } = {}) {
  const row = rows[0];
  const target = onRow ? row : {};
  const matches = (sel) => sel.split(',').map((p) => p.trim()).some((part) =>
    tokens.some((t) => part === t || part.startsWith(t + ':') || part.startsWith(t + '[')));
  if (!onRow) {
    target.closest = (sel) => (matches(sel) ? target : sel === 'li' ? row : null);
  } else {
    row.closest = (sel) => (sel === 'li' ? row : null);
  }
  let prevented = false;
  handler({ key, target, preventDefault() { prevented = true; } });
  return { prevented, moved: calls.splice(0).filter((c) => c.startsWith('focus')) };
}
process.stdout.write(JSON.stringify({
  %(probes)s
}));
"""


def _run(probes: str) -> dict:
    source = app_js_text()
    match = re.search(r"^function initEntryListKeyboardNav\(\) \{.*?^\}", source, re.S | re.M)
    assert match, "initEntryListKeyboardNav is gone"
    script = HARNESS % {"source": match.group(0), "probes": probes}
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


FIELDS = {
    "title input": '["input"]',
    "tags input": '["input"]',
    "plain textarea": '["textarea"]',
    "live editor": '[".cm-content", "[contenteditable]", ".cm-editor"]',
}


@pytest.mark.parametrize("key", ["Home", "End", "ArrowUp", "ArrowDown"])
@pytest.mark.parametrize("field", sorted(FIELDS))
def test_a_text_field_inside_a_row_keeps_its_navigation_keys(field, key):
    result = _run(f'r: press("{key}", {FIELDS[field]})')["r"]
    assert result["prevented"] is False, f"{key} in the {field} was swallowed by the list"
    assert result["moved"] == [], f"{key} in the {field} moved focus to another row"


@pytest.mark.parametrize("key", ["Home", "End", "ArrowDown", "ArrowUp"])
def test_the_row_itself_still_moves_between_rows(key):
    result = _run(f'r: press("{key}", [], {{ onRow: true }})')["r"]
    assert result["prevented"] is True
    assert len(result["moved"]) == 1
