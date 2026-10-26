"""Code editor and recordings leftovers (the 2026-10-26 dogfood).

Four things the owner's pass found: the status bar counted words in a code
file, the Assistant's send did nothing visible on an empty prompt, a code file
had no print path of its own, and the recordings waveform was 40px tall.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DOCS_JS = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
CODEKIT_JS = (FRONTEND / "js" / "documents-codekit.js").read_text(encoding="utf-8")
SETTINGS_JS = (FRONTEND / "js" / "settings-wiring.js").read_text(encoding="utf-8")
INDEX = (FRONTEND / "index.html").read_text(encoding="utf-8")
node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _function(source: str, name: str) -> str:
    """One top-level function's text: the scripts keep them at column 0."""
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _run(names: list[tuple[str, str]], call: str):
    body = "\n".join(_function(src, name) for src, name in names)
    script = f"const TEXT_READING_WPM = 220;\n{body}\nconsole.log(JSON.stringify({call}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def _css(name: str) -> str:
    return (FRONTEND / "css" / name).read_text(encoding="utf-8")


# --- 1. the status bar of a code file ---------------------------------------


@node
def test_a_code_file_counts_lines_characters_and_language_not_words():
    names = [
        (SETTINGS_JS, "textCounts"),
        (DOCS_JS, "docLineCount"),
        (DOCS_JS, "docCodeCountsText"),
    ]
    text = _run(names, 'docCodeCountsText("def f(x):\\n    return x * 2\\n", "Python")')
    assert text == "2 lines · 27 chars · Python"
    assert "word" not in text and "read" not in text
    assert _run(names, 'docCodeCountsText("x", "C")') == "1 line · 1 char · C"
    assert _run(names, 'docCodeCountsText("", "Bash")') == "0 lines · 0 chars · Bash"


def test_the_status_bar_picks_the_code_line_the_way_the_chord_guard_does():
    block = _function(DOCS_JS, "renderDocCounts")
    assert "docIsCodeFile()" in block and "docCodeCountsText(" in _function(DOCS_JS, "renderDocCodeCounts")
    # docIsCodeFile is the previewable test docProseChord makes, less the
    # prose-like txt and csv, which keep their word counts.
    assert "!type.previewable" in _function(DOCS_JS, "docIsCodeFile")
    assert "previewable" in _function(DOCS_JS, "docProseChord")
