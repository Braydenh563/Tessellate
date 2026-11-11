"""The capture box's draft never keeps or restores whitespace alone.

The owner, 2026-09-27: "sometimes when I load up the app, there is randomly
3 new lines in the main note capture text box meaning the help text that
shows when it is empty doesnt show". A textarea's placeholder only shows when
its value is exactly "", so blank lines saved as a "draft" and restored on
the next load hide it. Both ends are guarded: the input handler does not
save a blank draft, and the restore drops one that an older build saved.
"""

import re

from tests._app_js import app_js_text


def _draft_code():
    text = app_js_text()
    start = text.index('$("entry-content").addEventListener("input"')
    end = text.index("renderEntryAttachmentChips();", text.index('prefs.get("captureDraft", null)'))
    return text[start:end]


def test_a_blank_draft_is_not_saved():
    code = _draft_code()
    saved = re.search(r'^\s*if \((.*)\) prefs\.set\("captureDraft"', code, re.M)
    assert saved, "the draft save moved; update this test"
    assert ".trim()" in saved.group(1), "a whitespace-only draft must not be saved"


def test_a_blank_draft_is_not_restored():
    code = _draft_code()
    restore = code[code.index('prefs.get("captureDraft", null)') :]
    guard = restore.index("if (!draft.trim())")
    assert guard < restore.index("box.value = draft"), "blank drafts must be dropped before the box is filled"
    assert 'prefs.remove("captureDraft")' in restore[guard : guard + 200]


# --- the draft is written after a pause, from the box as it is then ----------------

HARNESS = r"""
const vm = require("vm");
const timers = new Map(); let next = 1, now = 0;
const writes = [], on = {};
const box = { value: "", draftTimer: 0, addEventListener: (t, f) => { on.input = f; } };
const ctx = {
  $: () => box, document: { hidden: false, addEventListener: (t, f) => { on.visibility = f; } },
  window: { addEventListener: (t, f) => { on.pagehide = f; } },
  prefs: { set: (k, v) => writes.push(["set", v]), remove: () => writes.push(["remove"]) },
  setTimeout: (f, ms) => { timers.set(next, [f, now + ms]); return next++; },
  clearTimeout: (id) => timers.delete(id),
};
const advance = (ms) => { now += ms; for (const [id, [f, at]] of [...timers]) if (at <= now) { timers.delete(id); f(); } };
vm.createContext(ctx);
vm.runInContext(process.argv[1], ctx);
const out = {};
for (const c of "hello") { box.value += c; on.input(); advance(100); }
out.beforePause = writes.length;
advance(400);
out.afterPause = writes.slice();
writes.length = 0;
box.value = "typed"; on.input(); box.value = ""; advance(400);
out.cleared = writes.slice();
writes.length = 0;
box.value = "late"; on.input(); on.pagehide();
out.hide = writes.slice();
writes.length = 0;
on.pagehide(); advance(1000);
out.idle = writes.slice();
process.stdout.write(JSON.stringify(out));
"""


def test_the_draft_is_written_after_a_pause_and_a_cleared_box_writes_nothing() -> None:
    import json
    import shutil
    import subprocess

    import pytest

    if not shutil.which("node"):
        pytest.skip("needs node")
    text = app_js_text()
    start = text.index('{\n  const box = $("entry-content");\n  const flush')
    block = text[start : text.index("\n});\n", start) + 2]  # the block, now the body of its onSurface("notes") call
    proc = subprocess.run(["node", "-e", HARNESS, block], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-1500:]
    out = json.loads(proc.stdout)
    assert out["beforePause"] == 0, "no write while the person is typing"
    assert out["afterPause"] == [["set", "hello"]], "one write after the pause, of the whole text"
    assert out["cleared"] == [["remove"]], "a box emptied in the pause removes the draft, it never writes the old text"
    assert out["hide"] == [["set", "late"]], "a pending write goes when the page is hidden"
    assert out["idle"] == [], "nothing pending, nothing written (another window's draft stays)"
