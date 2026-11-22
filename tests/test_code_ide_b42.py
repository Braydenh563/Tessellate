"""Brief 42: the code editor's VS Code pieces in `documents-ide.js`.

The merge view against a saved version, the minimap (off by default), fold
all and the problems panel in the palette, and Visual Basic. The pure parts
run in node against the vendored bundle; the wiring is read from the source.
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
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
IDE_JS = JS / "documents-ide.js"
CM_JS = ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


def _run_node(body: str) -> object:
    script = CM_JS.read_text(encoding="utf-8") + "\nconst CM = CM6;\n" + body
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


@node
def test_the_bundle_carries_the_kept_packages() -> None:
    got = _run_node(
        "console.log(JSON.stringify([typeof CM.merge.unifiedMergeView, typeof CM.merge.Chunk.build,"
        " typeof CM.showMinimap.compute, typeof CM.vb.token, typeof CM.vbScript.token, typeof CM.lint.openLintPanel,"
        " typeof CM.language.foldAll]));"
    )
    assert got == ["function"] * 7


#: Three hunks: a changed line, an inserted line, a deleted line.
_ORIGINAL = "one\ntwo\nthree\nfour\nfive\nsix\nseven\n"
_EDITED = "one\nTWO\nthree\nfour\nnew\nfive\nsix\n"


@node
@pytest.mark.parametrize("index", [0, 1, 2])
def test_reverting_one_hunk_restores_exactly_that_hunk(index: int) -> None:
    #: documents-ide.js is one closure now (ranked row 37a); these tests slice or run its private functions, so they read it as it was before it was wrapped (`_js_scope.unwrapped`): same code, same assertions.
    ide = _js_scope.unwrapped(IDE_JS.read_text(encoding="utf-8"))
    got = _run_node(
        _function(ide, "docIdeChunks")
        + _function(ide, "docIdeRevertSpec")
        + f"const orig = {json.dumps(_ORIGINAL)}, edited = {json.dumps(_EDITED)};\n"
        "const state = CM.state.EditorState.create({ doc: edited });\n"
        "const chunks = docIdeChunks(CM, orig, state);\n"
        f"const spec = docIdeRevertSpec(CM, orig, state, chunks[{index}]);\n"
        "const after = state.update(spec).state;\n"
        "console.log(JSON.stringify([chunks.length, after.doc.toString(), docIdeChunks(CM, orig, after).length]));"
    )
    count, after, left = got
    assert count == 3
    assert left == 2
    expected = [
        "one\ntwo\nthree\nfour\nnew\nfive\nsix\n",
        "one\nTWO\nthree\nfour\nfive\nsix\n",
        "one\nTWO\nthree\nfour\nnew\nfive\nsix\nseven\n",
    ][index]
    assert after == expected


def test_the_ide_file_is_lazy_and_mounted_from_the_code_tools() -> None:
    docs = documents_text()
    assert 'lazyScript("/js/documents-ide.js")' in docs
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "documents-ide.js" not in index, "lazy: not a boot script"
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    assert "docIdeExtensions(CM, type)" in _function(code, "docCompletionExtras")


def test_the_ide_file_waits_for_documents_js_before_it_is_fetched() -> None:
    """The idle warm-up loads the bundle a file at a time, so a fetch started as documents-view.js runs executed
    documents-ide.js before documents.js defined `docToolPref` (found driving the attach-to path, dec-1111-d2)."""
    view = (JS / "documents-view.js").read_text(encoding="utf-8")
    assert 'lazyScript("/js/documents.js").then(() => lazyScript("/js/documents-ide.js"))' in view
    assert not re.search(r'^lazyScript\("/js/documents-ide\.js"\)', view, re.M), "a bare top-level fetch races documents.js"


def test_the_minimap_is_off_by_default_and_a_view_toggle() -> None:
    ide = _js_scope.unwrapped(IDE_JS.read_text(encoding="utf-8"))
    assert 'docToolPref("codeMinimap", false)' in ide
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="doc-minimap-row"' in index and 'id="doc-minimap"' in index


def test_the_palette_rows_have_a_shortcut_or_say_none() -> None:
    docs = documents_text()
    table = docs[docs.index("// DOC-COMMANDS-BEGIN") : docs.index("// DOC-COMMANDS-END")]
    for cid, keys in [
        ("fold-all", "Ctrl+Alt+["),
        ("unfold-all", "Ctrl+Alt+]"),
        ("problems", "Ctrl+Shift+M"),
        ("minimap", "none"),
        ("compare-version", "none"),
        ("compare-revert", "none"),
        ("compare-stop", "none"),
    ]:
        row = re.search(r'\{ id: "' + re.escape(cid) + r'".*?keys: "([^"]*)"', table, re.S)
        assert row, cid
        assert row.group(1) == keys, cid


def test_help_names_the_new_commands() -> None:
    guide = help_chat_text()
    for words in ("minimap", "Compare with a saved version", "Ctrl+Shift+M"):
        assert words in guide, words


# --- INBOX 736: the output panel's height and the Stop button ---------------------


def test_the_output_panel_has_the_sidebar_grip_with_keys_and_a_height_per_document() -> None:
    ide = _js_scope.unwrapped(IDE_JS.read_text(encoding="utf-8"))
    grip = _function(ide, "docIdeRunGrip")
    assert '"sidebar-resize doc-run-resize"' in grip
    assert '"separator"' in grip and '"horizontal"' in grip and "tabindex" in grip
    for key in ("ArrowUp", "ArrowDown", "Home", "dblclick", "pointerdown"):
        assert key in grip, key
    assert "currentDoc.id" in _function(ide, "docIdeRunSaveHeight")
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    assert "docIdeRunGrip(dom" in _function(code, "docRunPanel")


def test_stop_is_disabled_once_a_script_has_nothing_left_to_run() -> None:
    sandbox = (ROOT / "src" / "tessellate" / "api" / "run_sandbox_assets" / "sandbox_page.html").read_text(encoding="utf-8")
    #: The worker counts its own timers and says when the last one is gone.
    assert "t:'idle'" in sandbox and "pending:" in sandbox
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    listener = code[code.index('if (data.t === "done")') : code.index('if (data.t !== "log") return;')]
    assert 'docRunSetStatus("Finished.", false)' in listener
    assert 'data.t === "idle"' in listener


def test_no_class_is_written_onto_the_engines_own_dom() -> None:
    """CodeMirror owns `view.dom`'s class attribute and rewrites it on every
    focus change, so `.doc-content-code` toggled there by `syncDocFileType`
    was gone at the first focus (docs42). A class the editor wears is
    declared through `editorAttributes`; this greps for the shape that loses
    it: a class written through `docSurface()` (whose `classList` is the
    view's when the engine is mounted) or straight onto `docCmView.dom`."""
    bad = re.compile(
        r"(docSurface\(\)\??\.classList|docCmView\??\.dom\??\.classList)\.(add|remove|toggle|replace)\("
    )
    hits = [
        f"{path.name}:{n}"
        for path in sorted(JS.glob("*.js"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if bad.search(line)
    ]
    assert hits == [], f"a class written onto CodeMirror's own DOM: {hits}"
    ide = _js_scope.unwrapped((JS / "documents-ide.js").read_text(encoding="utf-8"))
    assert 'editorAttributes.of({ class: "doc-content-code" })' in ide
    sync = _function(documents_text(), "syncDocFileType")
    assert 'docBoxEl()?.classList.toggle("doc-content-code", code)' in sync
