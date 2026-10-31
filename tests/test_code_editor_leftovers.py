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
    #: `textCounts` counts words through the one helper (`wordCount`, settings-wiring.js).
    counter = SETTINGS_JS[SETTINGS_JS.index("const WORD_PER_CHARACTER") : SETTINGS_JS.index("function textCounts(")]
    script = f"const TEXT_READING_WPM = 220;\n{counter}\n{body}\nconsole.log(JSON.stringify({call}));"
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


# --- 2. an empty Assistant prompt -------------------------------------------


def test_an_empty_assistant_prompt_is_shown_at_the_field_not_far_below_it():
    ask = _function(CODEKIT_JS, "docAssistAsk")
    assert "docAssistEmptyAsk()" in ask
    assert 'docAssistSay("Type a question first.")' not in ask
    empty = _function(CODEKIT_JS, "docAssistEmptyAsk")
    assert "focus()" in empty and 'aria-invalid' in empty and "doc-assist-hint" in empty
    hint = re.search(r'<p id="doc-assist-hint"[^>]*>', INDEX)
    assert hint, "the hint sits in the markup, under the field"
    assert 'role="status"' in hint.group(0) and "hidden" in hint.group(0)
    assert INDEX.index('id="doc-assist-form"') < INDEX.index('id="doc-assist-hint"') < INDEX.index('id="doc-assist-answer"')
    # Typing clears it, so it never outlives the reason for it.
    assert re.search(r'\$\("doc-assist-question"\)\.addEventListener\("input", docAssistClearHint\)', CODEKIT_JS)
    assert "Type a question first." in INDEX


def test_the_invalid_field_is_drawn_in_the_error_ink():
    css = _css("library-lazy.css")
    assert re.search(r'\.search-field\.doc-assist-form:has\(\[aria-invalid="true"\]\)[^{]*\{[^}]*--error', css)


# --- 3. printing a code file ------------------------------------------------


@node
def test_a_code_file_prints_one_row_per_line_without_a_phantom_last_row():
    names = [(DOCS_JS, "docCodePrintRows")]
    assert _run(names, 'docCodePrintRows("a\\nb\\n")') == ["a", "b"]
    assert _run(names, 'docCodePrintRows("a\\r\\n\\r\\nb")') == ["a", "", "b"]
    assert _run(names, 'docCodePrintRows("")') == []


def test_a_code_file_has_a_print_row_and_prints_its_own_listing():
    hidden = re.search(r'for \(const id of \[([^\]]*)\]\) \$\(id\)\?\.classList\.toggle\("hidden", docIsCodeFile\(\)\)', DOCS_JS)
    assert hidden and "doc-export-pdf" not in hidden.group(1)
    assert "docCodeExportRefused" not in _function(DOCS_JS, "exportDocumentPdf")
    begin = _function(DOCS_JS, "docPrintBegin")
    assert "docIsCodeFile()" in begin and "docCodePrintFill()" in begin
    fill = _function(DOCS_JS, "docCodePrintFill")
    assert "doc-code-print-line" in fill and "doc-code-print-no" in fill
    assert "docPrintBegin()" in DOCS_JS.split('window.addEventListener("beforeprint"')[1][:500]


def test_the_printed_code_is_monospaced_with_numbers_and_keeps_a_line_whole():
    css = _css("library-lazy.css")  # lazy: the boot stylesheets have a byte cap
    assert "@media print" in css
    row = re.search(r"body\.printing-doc \.doc-code-print-line \{[^}]*\}", css)
    assert row and "break-inside: avoid" in row.group(0)
    text = re.search(r"body\.printing-doc \.doc-code-print \{[^}]*\}", css)
    assert text and text.group(0).count("monospace") == 1 and "ui-monospace" not in text.group(0)
    number = re.search(r"body\.printing-doc \.doc-code-print-no \{[^}]*\}", css)
    assert number and "text-align: right" in number.group(0) and "tabular-nums" in number.group(0)


# --- 4. the recordings waveform ---------------------------------------------


def test_the_recording_waveform_is_taller_than_a_touch_target_and_stays_on_tokens():
    css = _css("meetings-lazy.css")
    rule = re.search(r"\n\.recording-wave \{[^}]*\}", css).group(0)
    assert "height: calc(var(--control-h-touch) * 1.6)" in rule
    assert not re.search(r"height:\s*\d+px", rule)
    phone = re.search(r"@media \(max-width: 599\.98px\) \{\s*\.recording-wave \{[^}]*\}", css)
    assert phone and "calc(var(--control-h-touch) * 1.2)" in phone.group(0)
