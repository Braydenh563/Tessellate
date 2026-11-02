"""audit-1031 Z10: a script that is one closure is on the map too.

sketch-pad.js is `(() => { ... })()` from its first line to its last, so a map
that reads only column 0 listed none of its 143 functions. Lifting them into
the page's one global scope would clash with the app's own `icon`, `h`, `say`,
`open` and `undo` and break the pad's promise to read nothing global, so the
map reads the closure instead: in a file that is wrapped whole, a function
indented one step is listed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _codemap():
    spec = importlib.util.spec_from_file_location("codemap", ROOT / "scripts" / "codemap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _found(source: str) -> list[str]:
    return [name for name, _line in _codemap().js_functions(source.splitlines())]


def test_a_wrapped_file_lists_the_closures_functions():
    source = "// header\n\n(() => {\n  \"use strict\";\n  function a() {}\n  async function b() {}\n  const c = (x) => x;\n    function nested() {}\n})();\n"
    assert _found(source) == ["a", "b", "c"]


def test_a_file_with_an_iife_in_the_middle_keeps_column_zero_only():
    source = "function top() {}\n(() => {\n  function inner() {}\n})();\nfunction after() {}\n"
    assert _found(source) == ["top", "after"]


def test_the_sketch_pad_is_on_the_map():
    text = (ROOT / "docs" / "CODEMAP.md").read_text(encoding="utf-8")
    assert "| `saveNote` | frontend/js/sketch-pad.js:" in text
    assert "| `floodFill` |" in text or "| `fit` | frontend/js/sketch-pad.js:" in text
