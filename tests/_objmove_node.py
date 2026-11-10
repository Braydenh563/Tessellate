"""Node harness for the object-move scripts (INBOX 1467): their pure parts run
in a `vm` context with a handful of stubs, and the test reads JSON back.
Skipped where node is not installed."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const files = JSON.parse(process.argv[1]);  // [name, source] pairs
const log = [];
const handlers = {};
const ctx = {
  sortEntries: (entries) => entries, noteSort: "newest",
  handlers, addEventListener: () => {}, removeEventListener: () => {},
  console, Math, Number, Object, Set, Map, JSON, Date, Array, String, RegExp, Promise, Boolean,
  log, setTimeout: () => 0, clearTimeout: () => {}, dragHold: () => {}, dragRelease: () => {},
  document: {
    execCommand: () => true, activeElement: null, querySelector: () => null, querySelectorAll: () => [], documentElement: { dataset: {} },
    addEventListener: (type, fn) => { (handlers[type] = handlers[type] || []).push(fn); }, removeEventListener: () => {},
  },
  allEntries: [{ id: 5, title: "", content: "# Five\n\nbody" }],
  noteNamePlain: (text) => String(text).replace(/^#+\s*/, "").split("\n")[0],
  attachedNoteIds: [], attachedImages: [], renderAttachments: () => log.push("renderAttachments"),
  renderImageAttachments: () => log.push("renderImageAttachments"),
  attachDocumentToChat: (id, name) => { log.push(["doc", id, name]); return true; },
  attachBoardToChat: (id, name) => { log.push(["board", id, name]); return true; },
  attachLibraryFile: (id, name) => { log.push(["file", id, name]); return true; },
  $: () => null, lazyScript: (file) => log.push(["lazy", file]),
};
ctx.window = ctx;
vm.createContext(ctx);
for (const [file, source] of files) vm.runInContext(source, ctx, { filename: file });
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
"""


def run(files: list[str], body: str):
    """Run `body` (JS) after loading `files`; it calls `__out(value)` once."""
    #: A wrapped script (ranked row 37a) is run without its closure lines: these tests call its
    #: private names, and the code they check is the file's own (`_js_scope.unwrapped`).
    paths = [[name, _js_scope.unwrapped((JS / name).read_text(encoding="utf-8"))] for name in files]
    proc = subprocess.run(
        ["node", "-e", HARNESS + "\nvm.runInContext(process.argv[2], ctx);", json.dumps(paths), body],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout)
