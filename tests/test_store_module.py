"""The page's shared state has one owner, a slice at a time (WORLD_CLASS_PLAN 10, F12).

`frontend/js/store.js` holds a slice's one current value; surfaces subscribe
instead of keeping a copy. The first slice is `notes`: `loadEntries` publishes
every list it lands in `allEntries` (both writers), and the dashboard's
notebook-wide widgets wait for that slice rather than asking `/entries` for
the same rows a second time at boot.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"


def _node(script: str) -> str:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_set_get_subscribe_and_when() -> None:
    store = JS / "store.js"
    script = f"""
eval(require("fs").readFileSync({str(store)!r}, "utf8") + "; globalThis.appState = appState; globalThis.publishNotes = publishNotes;");
(async () => {{
  const out = [];
  out.push(String(appState.has("notes")));
  const waiting = appState.when("notes", 1000);
  const seen = [];
  const off = appState.subscribe("notes", (v) => seen.push(v.length));
  appState.subscribe("notes", () => {{ throw new Error("one bad subscriber"); }});
  publishNotes([1, 2]);
  publishNotes([1, 2, 3]);
  off();
  publishNotes([]);
  out.push(JSON.stringify(await waiting));
  out.push(seen.join(","));
  out.push(String(appState.has("notes")) + ":" + appState.get("notes").length);
  out.push(String(await appState.when("never", 20)));
  console.log(out.join("|"));
}})();
"""
    assert _node(script).split("|") == ["false", "[1,2]", "2,3", "true:0", "null"]


def test_both_writers_of_the_notes_list_publish_it() -> None:
    #: The semantic search's write moved to the lazy notes-lazy.js (`loadSemanticEntries`, INBOX 1525, for the boot
    #: gzip budget): the rule is about every writer, wherever it lives, so both files are read.
    notes = "\n".join((JS / name).read_text(encoding="utf-8") for name in ("notes-list.js", "notes-lazy.js"))
    writes = notes.count("allEntries = ")
    # The full read, the semantic search and `refreshEntries`'s patch.
    assert writes == 3
    assert notes.count("publishNotes(allEntries)") == writes


def test_the_dashboard_waits_for_the_slice_instead_of_refetching() -> None:
    dash = (JS / "dashboard.js").read_text(encoding="utf-8")
    body = dash[dash.index("async function dashEntries()") :]
    body = body[: body.index("\n}\n")]
    assert 'appState.when("notes"' in body


def test_the_notes_list_follows_the_cursor() -> None:
    notes = (JS / "notes-list.js").read_text(encoding="utf-8")
    body = notes[notes.index("async function _loadEntries()") :]
    body = body[: body.index("\n}\n")]
    assert 'response.headers.get("X-Next-Cursor")' in body
    assert "&offset=" not in body
