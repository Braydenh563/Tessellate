"""Edit on a phone's note page opens the form where it can be seen.

At phone width a tapped note opens as a full-page sheet (`openNotePage`,
frontend/js/phone-shell.js) and its Edit button is `openNoteEditor`
(notes-list.js), which opens the edit form in the Your notes list. The list is
behind the sheet, so Edit did nothing anyone could see: the sheet stayed
over a form nobody could reach until Back was pressed. Found by
`scratchpad/ui-sweeps/deepflows.js` at 390 wide (the edit form's title box was
under `.note-page-list`, `elementFromPoint` at its centre).

The fix is that starting an edit puts the sheet away first.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import app_js_text

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(setup: str, call: str, may_close: bool = True) -> dict:
    source = app_js_text()
    match = re.search(r"^async function openNoteEditor\(.*?^\}", source, re.S | re.M)
    assert match, "openNoteEditor is gone"
    script = f"""
const order = [];
let editingId = null, noteFormDirty = false, noteFormDraft = null;
const appState = {{ get: () => editingId }}; const setEditingNote = (id) => {{ editingId = id; }};
let focusTagsAfterRender = null, focusBodyAfterRender = null;
const requestAnimationFrame = (fn) => fn();
const scrollEditingEntryIntoView = () => order.push('scroll');
const renderEntries = () => order.push('render');
const noteFormMayClose = async () => {str(may_close).lower()};
{setup}
{match.group(0)}
(async () => {{
  const result = await {call};
  process.stdout.write(JSON.stringify({{ order, editingId, result }}));
}})();
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_the_phone_note_page_is_closed_before_the_form_is_drawn():
    got = _run("let notePageClose = () => order.push('close page');", "openNoteEditor(7)")
    assert got["editingId"] == 7
    assert got["order"][:2] == ["close page", "render"], got["order"]


def test_with_no_page_open_nothing_else_changes():
    got = _run("let notePageClose = null;", "openNoteEditor(7)")
    assert got["editingId"] == 7
    assert got["order"][0] == "render"


def test_a_refused_switch_leaves_the_page_where_it_was():
    got = _run(
        "let notePageClose = () => order.push('close page'); editingId = 3;",
        "openNoteEditor(7)",
        may_close=False,
    )
    assert got["result"] is False
    assert got["order"] == []
    assert got["editingId"] == 3
