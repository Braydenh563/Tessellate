"""Typing in a big code file stays cheap (audit 1031, row 23, CE3).

A 7,000-line .js file cost 9 to 17 ms a key and 36 long tasks in 20 keys at 4x
CPU. The whole-file passes that ran on every key, or on every pause, are now
windowed, mapped, cached or skipped. Text lints: the numbers are in the row.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
DOCS = documents_text()
CODE = (JS / "documents-code.js").read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def test_sticky_scroll_asks_for_the_symbols_around_one_position():
    symbols = _fn(CODE, "docCodeSymbols")
    assert "at = null" in symbols and "from: at, to: at" in symbols
    assert "docCodeSymbols(CM, view.state, ext, pos)" in CODE


def test_bracket_colours_map_on_a_key_and_recount_after_a_pause():
    assert "this.decorations.map(update.changes)" in CODE
    assert "later()" in CODE and "}, 200);" in CODE
    assert "destroy() {\n        clearTimeout(this.timer);" in CODE


def test_the_indent_guides_measure_the_space_when_the_face_changes():
    assert "docIndentGuides.fonts ||= new WeakMap()" in CODE
    assert "seen.get(view.contentDOM) === font" in CODE


def test_a_code_file_spell_check_reads_a_window():
    assert "function docCodeWindow(text)" in DOCS
    assert "text.length <= DOC_PROSE_WINDOW_CHARS) return null" in DOCS
    mask = _fn(DOCS, "docCodeProseMask")
    assert "win ? CM.language.syntaxTree(state)" in mask and "from: win.from, to: win.to" in mask
    assert "start: at + shift" in _fn(DOCS, "docCodeSpellFindings")


def test_a_code_file_skips_the_word_count_and_waits_longer_when_big():
    stats = _fn(DOCS, "renderDocStats")
    #: One word count for the bar and Statistics since DX10 (audit 1102): `docPlainText.counts`.
    assert stats.index("if (code) return;") < stats.index("docPlainText.counts(")
    delay = _fn(DOCS, "docFactsDelay")
    #: Was `len > 120000 && docIsCodeFile() ? 600 : 120`: the wait now grows with the
    #: length for prose as well (audit 1028 D20), a code file keeping its 600.
    assert re.search(r"len > 120000 \? 600 : len > 40000 \? 300 : 120", delay)
    #: DX1 (audit 1102): the pass waits for a real pause, never less than this delay.
    assert "}, Math.max(docFactsDelay(), " in DOCS
