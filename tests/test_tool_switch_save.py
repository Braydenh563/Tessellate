"""A tool's switch in Settings puts itself back when the save is refused.

The handler on each switch in "Tools it can use" (frontend/js/skills.js)
awaited the save with nothing to catch it: a refused one (the preference once
held only 50 names, see `tests/test_agent_tools_api.py`) was an unhandled
rejection and the switch stayed where the server disagreed with it. Found by
`scratchpad/ui-sweeps/deepflows.js` switching every tool off.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import app_js_text

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _grab(source: str):
    """The save queue and the switch's save, as one block of source."""
    match = re.search(r"^ *let toolSaves = .*?^ *function saveToolSwitch\(.*?applyToolFilter\(\);\n *\}\);\n *\}", source, re.S | re.M)
    assert match, "the tool save queue or saveToolSwitch is gone"
    return match


def _run(save: str, checked: bool) -> dict:
    source = app_js_text()
    match = _grab(source)
    script = f"""
let prefsCache = {{ disabled_tools: ['a'] }};
const calls = [];
const toasts = [];
const applyToolFilter = () => calls.push('filter');
const toast = (text, isError) => toasts.push([text, Boolean(isError)]);
const apiJson = async (path, options) => {{ calls.push(JSON.parse(options.body).disabled_tools); {save} }};
{match.group(0)}
(async () => {{
  const check = {{ checked: {str(checked).lower()} }};
  await saveToolSwitch(check, 'b');
  process.stdout.write(JSON.stringify({{ checked: check.checked, calls, toasts, prefs: prefsCache }}));
}})();
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_a_saved_switch_off_adds_the_tool_and_redraws_the_count():
    got = _run("return { disabled_tools: ['a', 'b'] };", checked=False)
    assert got["calls"] == [["a", "b"], "filter"]
    assert got["checked"] is False and got["toasts"] == []


def test_a_refused_save_puts_the_switch_back_and_says_why():
    got = _run("throw new Error('Check the disabled tools and try again.');", checked=False)
    assert got["checked"] is True  # it was switched off by the press; refused, so back on
    assert got["toasts"] == [["Check the disabled tools and try again.", True]]
    assert "filter" not in got["calls"]
    assert got["prefs"] == {"disabled_tools": ["a"]}


def test_a_refused_switch_on_goes_back_off():
    got = _run("throw new Error('no');", checked=True)
    assert got["checked"] is False


def test_two_quick_presses_do_not_lose_the_first():
    """Both presses read the list as the first PUT left it: the second used to start
    from the old one and drop the first's change (deepflows, a tool back on after reload)."""
    script = f"""
let prefsCache = {{ disabled_tools: [] }};
const sent = [];
const applyToolFilter = () => {{}};
const toast = () => {{}};
const apiJson = (path, options) => new Promise((resolve) => {{
  const body = JSON.parse(options.body);
  sent.push(body.disabled_tools);
  setTimeout(() => resolve(body), 20);
}});
{_grab(app_js_text()).group(0)}
(async () => {{
  const a = {{ checked: false }};
  const b = {{ checked: false }};
  await Promise.all([saveToolSwitch(a, 'a'), saveToolSwitch(b, 'b')]);
  process.stdout.write(JSON.stringify({{ sent, prefs: prefsCache }}));
}})();
"""
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert got["sent"] == [["a"], ["a", "b"]]
    assert got["prefs"] == {"disabled_tools": ["a", "b"]}
