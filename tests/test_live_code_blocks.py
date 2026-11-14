"""Live code blocks: a fenced block with a language is a code editor in Live.

The owner, 2026-10-07 and 2026-10-26: code blocks where "the code editor
works and code autofill and suggestions work for the stated language in that
codeblock". One editor, nested language parsing (the markdown parser mounts
the stated language on the block), so the block gets syntax colour, the
language's indentation and brackets and its completion, and the stored text
stays the same fenced Markdown. Pure parts run in node against the vendored
bundle; the wiring is read from the source; the drive is in CHANGELOG.
"""

from __future__ import annotations
from tests._app_js import frontend_text

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
BUNDLE = ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _read(name: str) -> str:
    return frontend_text(name) if name == "documents.js" else (JS / name).read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


def _region() -> str:
    text = _read("documents-prose.js")
    start, stop = text.index("// DOC-FENCE-BEGIN"), text.index("// DOC-FENCE-END")
    return text[start:stop]


def _run(expr: str) -> object:
    script = (
        "globalThis.window = globalThis; globalThis.self = globalThis;\n"
        + BUNDLE.read_text(encoding="utf-8")
        + "\nconst CM = window.CM6; function docPairInput() {}\n"
        + _function(_read("documents.js"), "docCmLanguageFor")
        + _region()
        + f"\nconsole.log(JSON.stringify({expr}));\n"
    )
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@node
def test_the_info_word_names_a_language() -> None:
    got = _run(
        "['python', 'JS', 'c++', 'python title=\"fit.py\"', 'yml', '{.sh}', 'mermaid', '', 'nope']"
        ".map(docPairInput.fenceExt)"
    )
    assert got == ["py", "js", "cpp", "py", "yaml", "bash", None, None, None]


@node
def test_the_markdown_parser_mounts_the_stated_language_on_the_block() -> None:
    expr = (
        "(() => { const md = CM.markdown.markdown({ base: CM.markdown.markdownLanguage,"
        " codeLanguages: (info) => docPairInput.fenceLanguage(CM, info) });"
        " const at = (text) => { const state = CM.state.EditorState.create({ doc: text, extensions: [md] });"
        " CM.language.ensureSyntaxTree(state, text.length, 5000);"
        " return CM.language.syntaxTree(state).resolveInner(text.indexOf('def') + 1, 1).name; };"
        " return { py: at('```python\\ndef f(x):\\n    return x\\n```\\n'),"
        " none: at('```mermaid\\ndef f(x)\\n```\\n'), plain: at('```\\ndef f(x):\\n```\\n') }; })()"
    )
    assert _run(expr) == {"py": "def", "none": "CodeText", "plain": "CodeText"}


@node
def test_each_language_package_brings_its_completion_source() -> None:
    expr = (
        "['js', 'ts', 'py', 'css', 'html', 'go'].map((e) =>"
        " docPairInput.fenceCompletersFor(CM, e).every((s) => typeof s === 'function')"
        " ? docPairInput.fenceCompletersFor(CM, e).length : -1)"
    )
    assert _run(expr) == [3, 3, 2, 1, 1, 0]


def test_the_wiring_is_in_place() -> None:
    docs = _read("documents.js")
    assert "codeLanguages:" in docs and "docPairInput.fenceLanguage(CM, info)" in docs
    # the completion in a fence follows the block's language; the info word completes
    assert "docPairInput.fenceSource(CM)" in _read("documents-code.js")
    assert "fenceInfo" in _region() and "fenceBody" in _region()


def test_code_inside_a_block_is_still_code_to_the_prose_checks() -> None:
    # a Python string sits twelve levels under its FencedCode, so the climb
    # out of the block's own tree must be deeper than the old six
    assert "k < 48" in _read("documents-prose.js")


def test_nothing_is_added_to_the_boot_scripts() -> None:
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "fenceLanguage" not in index
    assert "documents-fence" not in index


@node
def test_the_info_string_splits_into_language_and_title() -> None:
    got = _run(
        "['python title=\"fit.py\"', \"js title='a b.js'\", 'python', '', '{.sh}', 'title=\"x\"']"
        ".map(docPairInput.fenceParts)"
    )
    assert got == [
        {"language": "python", "title": "fit.py"},
        {"language": "js", "title": "a b.js"},
        {"language": "python", "title": ""},
        {"language": "", "title": ""},
        {"language": "sh", "title": ""},
        {"language": "", "title": "x"},
    ]


def test_live_draws_the_title_and_a_language_button() -> None:
    cm = _read("documents-cm.js")
    assert "docPairInput.fenceParts(" in cm
    assert "DocFenceLabelWidget" in cm
    assert "data-lang]::after" not in _read("documents-cm-theme.js")
