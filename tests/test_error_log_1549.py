"""An Error logged to the console reaches the app's log as text, never `{}` (INBOX 1549, 1111).

The owner's log read `ERROR: browser: CodeMirror plugin crashed: {}`, then
`ERROR browser {}`: the app's log (`recordBrowserLog`, app.js) wrote a non-string
with JSON.stringify, which gives "{}" for an Error, a DOMException, an ErrorEvent
and an Error from another realm. `recordBrowserLog.text` writes name, message and stack,
and the console.error wrapper in lag-watch.js hands the parts on as they are."""

from __future__ import annotations

import json
import subprocess

from tests._app_js import APP_JS, frontend_text

APP = APP_JS.read_text(encoding="utf-8")
LAG = frontend_text("lag-watch.js")


def _texts(cases: str) -> list[str]:
    start = APP.index("recordBrowserLog.text = (p) => {")
    body = APP[start : APP.index("\n};\n", start) + 4]
    script = f"const recordBrowserLog = {{}}; {body}\nconst browserLogText = recordBrowserLog.text; process.stdout.write(JSON.stringify([{cases}].map(browserLogText)));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_an_error_is_logged_as_its_stack():
    (out,) = _texts("new TypeError('x is not a function')")
    assert out.startswith("TypeError: x is not a function"), out
    assert "\n    at " in out, out


def test_an_error_without_a_stack_is_its_name_and_message():
    (out,) = _texts("Object.assign(new Error('boom'), { stack: '' })")
    assert out == "Error: boom", out


def test_no_part_is_a_bare_empty_object():
    out = _texts("{}, new Event('error'), new DOMException('gone', 'AbortError'), undefined, 5, { a: 1 }")
    assert out[:2] == ["[object Object]", "[object Event]"], out
    assert out[2].startswith("AbortError: gone"), out
    assert out[3:] == [None, "5", '{"a":1}'], out  # undefined joins as an empty string


def test_the_window_listeners_hand_the_error_itself_to_the_log():
    assert 'e.error || "",' in APP and "    e.reason,\n" in APP


def test_the_console_error_wrapper_hands_the_parts_on_untouched():
    start = LAG.index("  const original = console.error;")
    body = LAG[start : LAG.index("\n  };\n", start) + 5]
    script = (
        "const seen = []; const console = { error: (...p) => seen.push(p) };"
        "const lagNoteError = () => {}; const recordBrowserLog = { text: String };"
        f"{body}"
        "const e = new TypeError('x'); console.error('crashed:', e);"
        "process.stdout.write(JSON.stringify(seen[0][1] === e));"
    )
    assert subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout == "true"
