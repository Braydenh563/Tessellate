"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

L295 and L302: the Ctrl+K chord waits for its second key, and the keybindings
sheet shows the keys of where it was opened (F11 is Step into only while a
debug session is paused)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
IDE = (JS / "documents-ide.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = IDE.index(f"  function {name}(")
    return IDE[start : IDE.index("\n  }\n", start) + 5]


def test_ctrl_k_waits_for_the_second_chord_before_the_palette() -> None:
    """L295: Ctrl+K starts a wait; only Ctrl+S opens the sheet, and the palette
    opens at the end of the wait or on any other key, never before."""
    start = _function("docIdeChordStart")
    assert "DOC_IDE_CHORD_WAIT_MS" in start and "openPalette" not in start
    assert "openPalette" in _function("docIdeChordEnd")
    keydown = _function("docIdeKeydown")
    assert 'matchesShortcut(event, "Ctrl+K") && docIdeChordStart()' in keydown


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_sheet_shows_the_key_that_works_in_this_context() -> None:
    body = (
        "const DOC_IDE_STEP_IDS = ['debug-in', 'debug-out', 'debug-stop'];\n"
        + _function("docIdeKeysFor")
        + "\nconst focus = { id: 'focus', keys: 'F11' }, into = { id: 'debug-in', keys: 'F11 while debugging' };\n"
        "console.log(JSON.stringify([docIdeKeysFor(focus, {debugging: false}), docIdeKeysFor(focus, {debugging: true}),"
        " docIdeKeysFor(into, {debugging: false}), docIdeKeysFor(into, {debugging: true})]));"
    )
    out = subprocess.run(["node", "-"], input=body, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["F11", "None while debugging", "F11 while debugging", "F11"]


def test_the_sheet_has_no_code_section_in_a_prose_document() -> None:
    render = _function("docIdeRenderKeys")
    assert "context.code ? DOC_COMMANDS.filter" in render
    assert re.search(r"Debugging now \(F11 steps in\)", render) and "While debugging" in render
    assert "docIdeCodeView()" in _function("docIdeKeysContext")
