"""An Error logged to the console reaches the app's log as its stack (INBOX 1549).

The owner's log read `ERROR: browser: CodeMirror plugin crashed: {}`: CodeMirror
logs the Error object, and the app's log (`recordBrowserLog`, app.js) writes a
non-string with JSON.stringify, which gives "{}" for an Error. The lag watcher's
console.error wrapper, which runs first, hands it on as its stack."""

from __future__ import annotations

import json
import subprocess

from tests._app_js import frontend_text

LAG = frontend_text("lag-watch.js")


def test_the_console_error_wrapper_hands_an_error_on_as_its_stack():
    start = LAG.index("  const original = console.error;")
    body = LAG[start:LAG.index("\n  };\n", start) + 5]
    script = (
        "const seen = []; const console = { error: (...p) => seen.push(p) };"
        "const lagNoteError = () => {};"
        f"{body}"
        "console.error('CodeMirror plugin crashed:', new TypeError('x is not a function'));"
        "process.stdout.write(JSON.stringify(seen[0].map((p) => (typeof p === 'string' ? p : JSON.stringify(p)))));"
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out[0] == "CodeMirror plugin crashed:"
    assert out[1].startswith("TypeError: x is not a function"), out
