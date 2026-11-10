"""One reader of this browser's saved settings (WORLD_CLASS_PLAN section 10, F1).

"57 distinct `localStorage` keys read ad hoc, 14 of them `JSON.parse`d. This
is the shape of the worst UI bug in the project's history: a value invalid
where it is used, set somewhere else." By 2026-10-05 it was 224 direct reads
in the files after app.js, 29 of them parsed. `frontend/js/prefs.js` is now the one door: `prefs.get`
never throws (blocked or private-mode storage reads as empty) and never
returns `undefined`; `prefs.json` returns the shape asked for or the default;
`prefs.number` returns a finite number in range or the default, which is the
NaN class closed for the numbers that reach a layout (zoom, the graph's
gravity and spread).

The scripts that run before prefs.js are allowed their own reads: app.js (the
session token and the space, read by `api()`), and the two head shims that
run before anything else (theme-boot.js paints the theme before first paint,
boot-guard.js reports a page that failed to start).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import app_js_files, with_pieces

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
PREFS = JS / "prefs.js"

#: file -> direct `localStorage.getItem` calls it may make, and why.
ALLOWED = {
    "app.js": 3,  # runs before prefs.js: the token and the space for `api()`
    "theme-boot.js": 5,  # runs in <head> before first paint
    # Pages of their own (capture.html, clip.html) that load no prefs.js: the
    # session token, read once for their one request.
    "capture.js": 1,
    "clip.js": 1,
    # The 127.0.0.1 -> localhost carry-over page (origin-bridge.html): it moves
    # the raw keys, so it reads and writes them as they are, before prefs.js.
    "origin-bridge.js": 3,
}

GET = re.compile(r"localStorage\.getItem\(")


def _code(text: str) -> str:
    return "\n".join(
        "" if line.lstrip().startswith(("//", "*", "/*")) else line for line in text.splitlines()
    )


def test_no_direct_storage_read_outside_the_door() -> None:
    found = {}
    for path in sorted(JS.glob("*.js")):
        n = len(GET.findall(_code(path.read_text(encoding="utf-8"))))
        if n:
            found[path.name] = n
    extra = {name: n for name, n in found.items() if n > ALLOWED.get(name, 0)}
    assert not extra, f"read saved settings through prefs.get/json/number, not localStorage: {extra}"


#: file -> direct `localStorage.setItem`/`removeItem` calls it may make. The
#: writes followed the reads through the door on 2026-10-11 (SESSION_BRIEFS
#: Brief 3): 281 calls in 48 files, each a `try` around a write that can throw
#: in a private window, now `prefs.set` (which answers false instead) and
#: `prefs.remove`. What stays is what runs before prefs.js: app.js writes and
#: clears the session token.
WRITES_ALLOWED = {"app.js": 2, "origin-bridge.js": 2}  # the carry-over page, as above

WRITE = re.compile(r"localStorage\.(?:setItem|removeItem)\(")


def test_no_direct_storage_write_outside_the_door() -> None:
    found = {}
    for path in sorted(JS.glob("*.js")):
        if path.name == "prefs.js":
            continue
        n = len(WRITE.findall(_code(path.read_text(encoding="utf-8"))))
        if n:
            found[path.name] = n
    extra = {name: n for name, n in found.items() if n > WRITES_ALLOWED.get(name, 0)}
    assert not extra, f"write saved settings through prefs.set/remove, not localStorage: {extra}"


def test_a_refused_write_still_reaches_the_callers_that_act_on_it() -> None:
    """Three writes act on a refusal: the quick note outbox keeps the words on
    screen, and a notification row is not counted as kept. With the raw call
    they did it in a `catch`; through `prefs.set` they read its answer."""
    outbox = (JS / "quick-note.js").read_text(encoding="utf-8")
    assert "if (!prefs.set(NOTE_OUTBOX_KEY" in outbox
    status = with_pieces("status.js")
    assert status.count("if (!prefs.set(NOTIFICATIONS_KEY") >= 2


def test_prefs_loads_right_after_app_js() -> None:
    names = [path.name for path in app_js_files()]
    assert names[:3] == ["app.js", "prefs.js", "store.js"], names[:4]


def test_no_json_parse_of_raw_storage_is_left() -> None:
    for path in sorted(JS.glob("*.js")):
        assert "JSON.parse(localStorage" not in path.read_text(encoding="utf-8"), path.name


def _node(script: str) -> str:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_prefs_never_throws_and_keeps_its_shapes() -> None:
    harness = f"""
const store = new Map();
let blocked = false;
globalThis.window = {{
  get localStorage() {{
    if (blocked) throw new Error("SecurityError");
    return {{
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
    }};
  }},
}};
eval(require("fs").readFileSync({str(PREFS)!r}, "utf8") + "; globalThis.prefs = prefs;");
const out = [];
store.set("list", "not json");
out.push(JSON.stringify(prefs.json("list", [])));
store.set("list", '{{"a":1}}');
out.push(JSON.stringify(prefs.json("list", [])));
store.set("obj", "[1,2]");
out.push(JSON.stringify(prefs.json("obj", {{}})));
store.set("graph-gravity", "abc");
out.push(String(prefs.number("graph-gravity", 50, {{ min: 0, max: 100 }})));
store.set("graph-gravity", "250");
out.push(String(prefs.number("graph-gravity", 50, {{ min: 0, max: 100 }})));
out.push(prefs.get("zoom"));
out.push(String(prefs.get("never-set", null)));
blocked = true;
out.push(String(prefs.get("anything", null)));
out.push(String(prefs.set("x", 1)));
console.log(out.join("|"));
"""
    assert _node(harness).split("|") == [
        "[]",  # not JSON: the default
        "[]",  # JSON, but not a list: the default
        "{}",  # a list where an object was asked: the default
        "50",  # NaN never leaves
        "100",  # clamped to the range
        "100",  # the schema's default for an unset key
        "null",  # getItem's null kept for a key with no schema default
        "null",  # blocked storage reads as empty
        "false",  # and a write to it is refused quietly
    ]
