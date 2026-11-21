"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

VC13: the rest of CodeMirror's lint and fold commands, in the editor and its palette.

Fold all, unfold all and the Problems tab were built in Brief 42 (`test_code_ide_b42.py`);
this holds toggle fold at the caret, the lint keymap and the in-editor problems list, and
that the prose panel already lists Harper's findings (LEDGER L316).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._help_text import help_chat_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CM_JS = ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js"


def _table() -> str:
    docs = (JS / "documents.js").read_text(encoding="utf-8") + (JS / "documents-view.js").read_text(encoding="utf-8")
    return docs[docs.index("// DOC-COMMANDS-BEGIN") : docs.index("// DOC-COMMANDS-END")]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_bundle_exports_what_the_editor_calls() -> None:
    body = (
        "const CM = CM6;\n"
        "console.log(JSON.stringify({fns: [typeof CM.lint.openLintPanel, typeof CM.language.toggleFold],"
        " keys: CM.lint.lintKeymap.map((k) => k.key)}));"
    )
    out = subprocess.run(["node", "-"], input=CM_JS.read_text(encoding="utf-8") + "\n" + body, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-1500:]
    got = json.loads(out.stdout)
    assert got["fns"] == ["function", "function"]
    assert "F8" in got["keys"] and "Mod-Shift-m" in got["keys"]


def test_toggle_fold_and_the_inline_problems_list_are_commands_with_keys() -> None:
    table = _table()
    for cid, keys in (("toggle-fold", "Ctrl+Alt+."), ("problems-inline", "none")):
        row = re.search(r'\{ id: "' + re.escape(cid) + r'".*?keys: "([^"]*)"', table, re.S)
        assert row and row.group(1) == keys, cid
    ide = (JS / "documents-ide.js").read_text(encoding="utf-8")
    assert "CM.language.toggleFold(view)" in ide and "CM.lint.openLintPanel(view)" in ide
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    assert "...CM.lint.lintKeymap" in code and '{ key: "Mod-Alt-.", run: CM.language.toggleFold }' in code


def test_the_guide_names_the_new_keys() -> None:
    guide = help_chat_text()
    assert "Ctrl+Alt+. toggles one" in guide


def test_the_prose_panel_lists_harper_findings_with_the_rest() -> None:
    """L316: a prose document's Problems list is the Writing suggestions panel, and
    Harper's findings (source "harper") are in the list it draws from."""
    prose = (JS / "documents-prose.js").read_text(encoding="utf-8")
    assert 'source: "harper"' in prose
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert "docGrammarFindings" in prose and "docProseFound" in docs
    assert 'id="doc-prose-panel"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
