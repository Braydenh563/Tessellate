"""On a phone, a tap in Select mode selects the note and nothing else.

A tapped note opens as a full-page sheet (`initNotePage`,
frontend/js/phone-shell.js). In Select mode the whole card is the checkbox
(note-cards.js), but the list's click handler had no idea of the mode, so the
first tap ticked the note *and* opened its page over the list; the next note
could not be reached without going back. Found by
`scratchpad/ui-sweeps/deepflows.js` (390 wide: the second row's click was
"intercepted" by the note page).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import JS_DIR

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _tap(select_mode: bool) -> list[int]:
    source = (JS_DIR / "phone-shell.js").read_text(encoding="utf-8")
    match = re.search(r"^function initNotePage\(\) \{.*?^\}", source, re.S | re.M)
    assert match, "initNotePage is gone"
    script = f"""
const opened = [];
let handler = null;
const PHONE_TABS = '(max-width: 599px)';
let selectMode = {str(select_mode).lower()};
const allEntries = [{{ id: 7 }}];
const openNotePage = (entry) => opened.push(entry.id);
const li = {{ dataset: {{ id: '7' }}, querySelector: () => null, classList: {{ contains: () => false }} }};
const target = {{ closest: (sel) => (sel.startsWith('li') ? li : null) }};
const document = {{ getElementById: () => ({{ addEventListener: (type, fn) => {{ handler = fn; }} }}) }};
const $ = (id) => document.getElementById(id);
const window = {{ matchMedia: () => ({{ matches: true }}), getSelection: () => '' }};
{match.group(0)}
initNotePage();
handler({{ target }});
process.stdout.write(JSON.stringify(opened));
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_a_tap_opens_the_note_page_outside_select_mode():
    assert _tap(select_mode=False) == [7]


def test_a_tap_in_select_mode_does_not_open_the_note_page():
    assert _tap(select_mode=True) == []
