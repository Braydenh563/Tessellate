"""Fenced code blocks are coloured by the vendored CodeMirror highlighter
(the owner, 2026-11-10), lazily and from the app's own tokens.

Measured in the browser by a Playwright run against a note with a ```python
block (numbers in CHANGELOG): keyword and string spans differ in computed
colour in light and in dark.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_renderer_asks_for_colour_only_for_a_fence_with_a_language() -> None:
    nav = _read(JS / "navigation.js")
    assert "else if (language) setTimeout(" in nav
    # the boot script holds only the trigger: the engine is a lazy module
    assert "highlightTree" not in nav
    assert "CM6" not in nav


def test_the_module_is_lazy_and_brings_its_stylesheet() -> None:
    entries = _read(JS / "lazy-entries.js")
    assert re.search(r'codeColour: \["/css/code-colour-lazy\.css", "/js/code-colour\.js"\]', entries)
    index = _read(ROOT / "frontend" / "index.html")
    assert "code-colour" not in index


def test_the_engine_reuses_the_vendored_bundle_and_adds_no_vendor_file() -> None:
    src = _read(JS / "code-colour.js")
    assert "/vendor/codemirror/codemirror.min.js" in src
    assert "CM.highlight.highlightTree" in src
    assert "classHighlighter" in src
    assert "innerHTML" not in src
    assert not (ROOT / "frontend" / "vendor" / "highlight.js").exists()


def test_the_stylesheet_uses_theme_tokens_only() -> None:
    css = _read(CSS / "code-colour-lazy.css")
    assert ".tok-keyword" in css and ".tok-string" in css and ".tok-comment" in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", css)
    for token in ("--accent-text", "--warn", "--muted"):
        assert f"var({token})" in css


def test_the_text_of_a_coloured_block_is_unchanged() -> None:
    # Copy and Save read the `text` the renderer kept, and the colouring only
    # wraps the same characters in spans (see `codeColourFill`).
    src = _read(JS / "code-colour.js")
    assert "codeEl.textContent !== text" in src
