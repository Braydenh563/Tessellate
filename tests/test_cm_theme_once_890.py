"""L-world-class-890: `docCmTheme` builds one CodeMirror theme per mode.

`EditorView.theme` mounts a new style module on every call and CodeMirror
keeps each module it mounted, so a theme built per editor kept about 90KB of
rules for every note opened: the ten-minute loop's heap grew 0.5MB a minute
(a sampling heap profile put 2.2MB of 2.7MB under `docCmTheme`). Run under
node with a fake CodeMirror that counts its theme calls."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def test_the_theme_is_built_once_per_mode_and_rebuilt_when_the_mode_changes():
    source = frontend_text("documents-cm-theme.js")
    script = r"""
const vm = require("vm");
let built = 0;
const CM = { view: { EditorView: { theme: (rules, opts) => ({ n: ++built, dark: opts.dark }) } } };
const ctx = { document: { documentElement: { dataset: { mode: "light" } } }, docIndentGuides: { levels: 24 }, docListGuides: () => ({}), Object, Array, Map };
// Every other helper the rules call is pure and returns rules: stubbed.
for (const [, name] of process.argv[1].matchAll(/\b(doc[A-Z]\w*)\(/g)) if (!(name in ctx) && name !== "docCmTheme" && name !== "docCmThemeBuild") ctx[name] = () => ({});
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(process.argv[1], ctx);
const a = ctx.docCmTheme(CM), b = ctx.docCmTheme(CM);
ctx.document.documentElement.dataset.mode = "dark";
const c = ctx.docCmTheme(CM), d = ctx.docCmTheme(CM);
process.stdout.write(JSON.stringify({ same: a === b, again: c === d, swapped: a !== c, dark: c.dark, built }));
"""
    done = subprocess.run(["node", "-e", script, source], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr[-600:]
    out = json.loads(done.stdout)
    assert out == {"same": True, "again": True, "swapped": True, "dark": True, "built": 2}
