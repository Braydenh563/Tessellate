"""Whole-line copy and cut with an empty selection, in every CM6 editor (INBOX 652).

The owner: "whole line copying or cutting when selected on the end of a line
etc, quality of life stuff". VS Code's rule. The behaviour itself is measured
in a browser (`scratchpad/ui-sweeps/linecopy.js`: clipboard text after Ctrl+C
and Ctrl+X, paste above the line, cut of the last line); these are the
ratchets that keep both editors wired to it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8") + (ROOT / "frontend" / "js" / "documents-view.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = DOCS.index(f"function {name}(")
    nxt = re.search(r"\n}\n", DOCS[start:])
    return DOCS[start : start + nxt.end()]


def test_the_handler_covers_copy_cut_and_paste():
    ext = _function("docLineClipboardExtension")
    assert "copy: docLineClipboardEvent" in ext
    assert "cut: docLineClipboardEvent" in ext
    assert "paste: docLinePasteEvent" in ext


def test_only_one_empty_caret_is_taken_over():
    rng = _function("docLineClipboardRange")
    assert "sel.ranges.length !== 1" in rng and "!sel.main.empty" in rng
    # The line travels with its newline, as VS Code puts it on the clipboard.
    assert "`${line.text}\\n`" in rng


def test_cutting_the_last_line_takes_the_newline_before_it():
    rng = _function("docLineClipboardRange")
    assert "line.from - 1" in rng


def test_a_cut_never_edits_a_read_only_view():
    assert "!view.state.readOnly" in _function("docLineClipboardEvent")
    assert "view.state.readOnly" in _function("docLinePasteEvent")


def test_both_editors_carry_it_ahead_of_the_other_paste_handlers():
    # The document's table and rich paste handlers sit lower, so a line-copy
    # is never mistaken for a table or HTML paste.
    assert "CM.state.Prec.high(docLineClipboardExtension(CM))" in _function("docCmExtensions")
    assert "CM.state.Prec.high(docLineClipboardExtension(CM))" in _function("noteSurfaceExtensions")
