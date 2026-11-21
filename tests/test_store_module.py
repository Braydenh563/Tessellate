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


#: The second slice, `reminders` (F12, L-world-class-81): the open reminders,
#: whole. One shared read (`openReminders`) sets it; the tab badge and the due
#: timer subscribe; the dashboard, the bell and the lock screen read it rather
#: than each keeping its own fetch of `/reminders`.
def test_open_reminders_is_one_shared_read_that_sets_the_slice() -> None:
    store = JS / "store.js"
    script = f"""
let calls = 0;
const pending = [];
globalThis.apiPagedList = (path) => {{ calls++; return new Promise((resolve) => pending.push([path, resolve])); }};
eval(require("fs").readFileSync({str(store)!r}, "utf8") + "; globalThis.appState = appState; globalThis.openReminders = openReminders; globalThis.remindersRead = remindersRead;");
(async () => {{
  const out = [];
  const seen = [];
  appState.subscribe("reminders", (rows) => seen.push(rows.length));
  const a = openReminders();
  const b = openReminders();
  out.push(String(a === b) + ":" + calls + ":" + pending[0][0]);
  // A forced read while the first is in flight: the older answer must not win.
  const c = openReminders(0);
  pending[1][1]([1, 2, 3]);
  await c;
  pending[0][1]([1]);
  await a;
  out.push(seen.join(",") + ":" + appState.get("reminders").length);
  out.push(String(await openReminders()) + ":" + calls);
  remindersRead.inflight = null;
  openReminders();
  out.push(String(calls));
  console.log(out.join("|"));
}})();
"""
    assert _node(script).split("|") == [
        "true:1:/reminders?include_done=false",
        "3:3",
        "1,2,3:2",
        "3",
    ]


def test_no_surface_keeps_its_own_copy_of_the_open_reminders() -> None:
    def body(name: str, head: str) -> str:
        text = (JS / name).read_text(encoding="utf-8")
        part = text[text.index(head) :]
        return part[: part.index("\n}\n")]

    dash = (JS / "dashboard.js").read_text(encoding="utf-8")
    assert "dashRemindersInflight" not in dash and 'apiPagedList("/reminders' not in dash
    assert dash.count("openReminders()") >= 3
    load = body("shell-reminders.js", "async function loadReminders()")
    assert "openReminders(0)" in load and 'apiPagedList("/reminders' not in load
    # The badge and the due timer follow the slice instead of being fed by hand.
    assert "armReminderTimer(" not in load and "updateReminderBadge(" not in load
    shell = (JS / "shell-reminders.js").read_text(encoding="utf-8")
    assert 'appState.subscribe("reminders"' in shell
    bell = body("notifications.js", "async function openNotifications(")
    assert 'apiJson("/reminders"' not in bell and "openReminders()" in bell
    tools = (JS / "utility-tools.js").read_text(encoding="utf-8")
    assert '"/reminders?include_done=false"' not in tools and "openReminders()" in tools
    swap = (JS / "space-swap.js").read_text(encoding="utf-8")
    assert "remindersRead.inflight = null" in swap
