"""Every PREFS_FILLS reader is called with no argument (renderPrefs: `read()`),
so one that takes `(p)` threw "Cannot read properties of undefined (reading
'notifications_muted_except_reminders')" on every opening of a Settings pane
that holds the switch, and stopped the fills after it."""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest
from tests._app_js import app_js_text

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def test_every_prefs_fill_reader_runs_with_the_cache_and_no_argument():
    fills = re.search(r"^const PREFS_FILLS = \[.*?^\];", app_js_text(), re.S | re.M)
    assert fills, "the field table moved"
    script = f"""
let prefsCache = {{ notifications_muted_except_reminders: true, new_notes_private: true }};
{fills.group(0)}
const out = {{}};
for (const [id, prop, read] of PREFS_FILLS) out[id] = read();
console.log(JSON.stringify([out['pref-notif-mute-except-reminders'], out['pref-new-notes-private']]));
"""
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=False)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "[true,true]"
