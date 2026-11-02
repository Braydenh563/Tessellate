"""A profile change waiting for its quiet save is not lost by switching panes.

Profile and General save themselves 700 ms after the last change
(`markPrefsDirty`, frontend/js/settings-panes.js). Opening any of the sections
that show those fields (`showSettingsSection`) runs `renderPrefs`, which asked
the server for the preferences and wrote them over the form. A change still
waiting for its save was overwritten by the old value, and then the timer saved
the form: the old value. Found by `scratchpad/ui-sweeps/deepflows.js`: switch
"Let Atlas read your name" on, go to General within the delay, reload, off.

The fields are written to the server before they are read back.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import app_js_text

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(dirty: bool, in_flight: bool) -> list[str]:
    source = app_js_text()
    match = re.search(r"^async function renderPrefs\(\) \{.*?^\}", source, re.S | re.M)
    assert match, "renderPrefs is gone"
    script = f"""
const order = [];
let prefsDirty = {str(dirty).lower()};
let prefsSaveInFlight = {'Promise.resolve().then(() => order.push("in flight settled"))' if in_flight else 'null'};
let prefsCache = null;
const element = () => new Proxy({{}}, {{ get: (t, k) => (k in t ? t[k] : undefined), set: (t, k, v) => {{ t[k] = v; return true; }} }});
const $ = () => element();
async function savePrefs(options) {{ order.push('save ' + JSON.stringify(options)); prefsDirty = false; }}
const apiJson = async () => {{ order.push('get'); return {{ profile_enabled: false }}; }};
const paintUserMarks = () => {{}};
const afterCharacters = () => {{}};
const updateProfileCount = () => {{}};
const markPrefsSaved = () => {{ prefsDirty = false; }};
{match.group(0)}
renderPrefs().then(() => process.stdout.write(JSON.stringify(order)));
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_a_change_waiting_for_its_save_is_saved_before_the_fields_are_read_back():
    order = _run(dirty=True, in_flight=False)
    assert order[0].startswith("save"), order
    assert order.index("get") > 0


def test_with_nothing_waiting_there_is_just_the_read():
    assert _run(dirty=False, in_flight=False) == ["get"]


def test_a_save_already_on_its_way_is_still_waited_for():
    order = _run(dirty=False, in_flight=True)
    assert order == ["in flight settled", "get"]
