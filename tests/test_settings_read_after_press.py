"""A read of /preferences begun before a switch's save does not put the switch back.

Opening Settings on Tools (or Background tasks, Web search, General) asks for
/preferences and writes what comes back over the switches. A press inside that
wait saved the new value, then the older answer landed and drew the switch as it
was: the deepflows settings sweep saw "pressing ... did not change it" on
`#pref-mcp-writes` (L-general-73). `setPreference.read` asks again when a save
started while it was waiting.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _piece(text: str, start: str) -> str:
    at = text.index(start)
    end = text.index("\n}\n", at) + 3
    return text[at:end]


@needs_node
def test_a_read_that_crossed_a_save_reads_again() -> None:
    panes = frontend_text("settings-panes.js")
    body = "\n".join(
        [
            _piece(panes, "async function setPreference("),
            panes[panes.index("setPreference.started = 0;"):panes.index("\n};\n", panes.index("setPreference.read = ")) + 4],
        ]
    )
    script = """
    let server = { mcp_writes_enabled: false };
    let prefsCache = null;
    const MIRRORED_PREFS = {};
    const $ = () => null;
    const toast = () => {};
    let gets = 0;
    //: The first GET is answered with what the server held when it was asked, after the save has landed.
    function apiJson(path, opts) {
      if (opts && opts.method === "PUT") {
        Object.assign(server, JSON.parse(opts.body));
        return Promise.resolve({ ...server });
      }
      gets += 1;
      const snapshot = { ...server };
      return new Promise((resolve) => setTimeout(() => resolve(gets === 1 ? snapshot : { ...server }), 20));
    }
    """ + body + """
    (async () => {
      const read = setPreference.read();
      await setPreference("mcp_writes_enabled", true);
      const prefs = await read;
      process.stdout.write(JSON.stringify({ seen: prefs.mcp_writes_enabled, gets }));
    })();
    """
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr[-1500:]
    assert json.loads(out.stdout) == {"seen": True, "gets": 2}


def test_every_section_that_fills_switches_on_open_reads_through_it() -> None:
    settings = frontend_text("settings.js")
    tools = settings[settings.index('if (name === "tools") {'):settings.index('if (name === "memory")')]
    tasks = settings[settings.index('if (name === "tasks") {'):]
    tasks = tasks[: tasks.index("\n  }\n")]
    for block in (tools, tasks):
        assert "setPreference.read()" in block and 'apiJson("/preferences")' not in block
    #: Web search's switches save through `setPreference`; General's are the form, which `renderPrefs`
    #: already saves before it reads (tests/test_prefs_pending_save_survives_pane_switch.py).
    prefs = frontend_text("settings-prefs.js")
    web = prefs[prefs.index("async function renderWebSearch("):]
    assert web.index("prefsCache = await setPreference.read();") < web.index("\n}\n")
