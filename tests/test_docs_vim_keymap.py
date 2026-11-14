"""The opt-in Vim keymap (L-documents-41): off by default, its own lazy file, shown in the dock.

`@replit/codemirror-vim` lives in `frontend/vendor/codemirror/vim.min.js`, a second file built against the
editor bundle's own `CM6` global (one copy of state and view), fetched only when the preference is on. The
real-key check (Escape then `dd`) is `scratchpad/ui-sweeps/vim-keys-l41.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope
from tests._help_text import help_chat_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
VENDOR = ROOT / "frontend" / "vendor" / "codemirror"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def test_the_vim_package_is_pinned_and_built_into_its_own_file() -> None:
    pins = json.loads((VENDOR / "package.json").read_text(encoding="utf-8"))["dependencies"]
    assert pins["@replit/codemirror-vim"] == "6.4.0"
    vim = (VENDOR / "vim.min.js").read_text(encoding="utf-8")
    assert vim.startswith("/*! @replit/codemirror-vim 6.4.0, MIT licence")
    assert "Object.assign(window.CM6,{vim:" in vim
    assert "vim.min.js" in (VENDOR / "build.sh").read_text(encoding="utf-8")
    assert "@replit/codemirror-vim" in (VENDOR / "LICENSE").read_text(encoding="utf-8")
    main = (VENDOR / "codemirror.min.js").read_text(encoding="utf-8")
    assert "vim-mode-change" not in main, "the editor bundle must not grow for an opt-in keymap"


@needs_node
def test_the_vim_file_adds_vim_and_Vim_to_the_editor_bundles_global() -> None:
    script = f"""
const fs = require("fs"), vm = require("vm");
const ctx = {{ console }}; ctx.window = ctx; vm.createContext(ctx);
const read = (f) => fs.readFileSync({json.dumps(str(VENDOR))} + "/" + f, "utf8");
vm.runInContext(read("codemirror.min.js") + ";globalThis.CM6 = CM6;", ctx);
const before = typeof ctx.CM6.vim;
vm.runInContext(read("vim.min.js"), ctx);
const state = vm.runInContext(`CM6.state.EditorState.create({{ doc: "a\\\\nb", extensions: [CM6.vim()] }}).doc.lines`, ctx);
console.log(JSON.stringify({{ before, vim: typeof ctx.CM6.vim, Vim: typeof ctx.CM6.Vim, getCM: typeof ctx.CM6.getCM, lines: state }}));
"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out == {"before": "undefined", "vim": "function", "Vim": "object", "getCM": "function", "lines": 2}


def test_the_setting_is_a_remembered_tool_preference_off_by_default() -> None:
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert re.search(r'vimKeys: "doc-vim"', docs)
    ide = _js_scope.unwrapped((JS / "documents-ide.js").read_text(encoding="utf-8"))
    assert 'docToolPref("vimKeys", false)' in ide
    assert 'docSaveToolPref("vimKeys"' in ide


def test_the_keymap_is_attached_only_when_the_setting_is_on() -> None:
    ide = _js_scope.unwrapped((JS / "documents-ide.js").read_text(encoding="utf-8"))
    vim = ide[ide.index("function docIdeVim(") : ide.index("function docIdeSlot(")]
    off = vim[: vim.index("return [];")]
    assert 'if (!docToolPref("vimKeys", false))' in off and "CM.vim()" not in off
    assert vim.count("CM.vim()") == 1 and "vim-mode-change" in vim
    assert "/vendor/codemirror/vim.min.js" in ide, "fetched on demand, never at boot"
    assert "vim.min.js" not in INDEX
    assert "docIdeVim(CM)" in ide[ide.index("function docIdeSlot(") :]


def test_the_row_and_the_mode_chip_are_in_the_dock() -> None:
    assert 'id="doc-vim-row"' in INDEX and 'id="doc-vim"' in INDEX
    row = INDEX[INDEX.index('id="doc-vim-row"') : INDEX.index('id="doc-vim-row"') + 600]
    assert "hidden" not in row.split(">")[0], "prose and code both take the keymap"
    chip = re.search(r'<span id="doc-vim-mode"[^>]*>', INDEX)
    assert chip and "dock-chip" in chip.group(0) and "hidden" in chip.group(0) and 'role="status"' in chip.group(0)


def test_the_mode_names_are_written_in_caps_by_the_ide_file() -> None:
    ide = (JS / "documents-ide.js").read_text(encoding="utf-8")
    for word in ("NORMAL", "INSERT", "VISUAL", "REPLACE"):
        assert word in ide


def test_help_and_the_guide_name_the_setting() -> None:
    dock_help = INDEX[INDEX.index('id="doc-dock-help"') : INDEX.index('id="doc-dock-help"') + 6000]
    assert "Vim keys" in dock_help
    assert "Vim keys" in help_chat_text() and "vim-keys" in help_chat_text()
    for text in (dock_help, help_chat_text()):
        assert "\u2014" not in text.split("Vim keys")[1][:400]
