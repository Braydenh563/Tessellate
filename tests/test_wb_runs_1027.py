"""Text runs on a board card (INBOX 1403): the inline bar on selected card text
sets a size, a font, a text colour and a highlight colour for that run only.

A run is stored in the text itself as `{{size=24 font=serif ink=red hl=yellow|words}}`
(like `==x==`, so save, search, undo and the AI all read it with no new column),
parsed by `INLINE_MD` in notes-list.js, drawn with classes and CSSOM (the CSP
forbids a `style=` attribute), and written out by the board's export as
per-run tspans. The pure parts run under node here; the page is measured by
`scratchpad/ui-sweeps/wb1027-runs.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NOTES = (JS / "notes-list.js").read_text(encoding="utf-8")
BOARD = (JS / "whiteboard.js").read_text(encoding="utf-8")
MAP = (JS / "whiteboard-map.js").read_text(encoding="utf-8")
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
EDITOR = (JS / "editor.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _const(source: str, name: str) -> str:
    start = source.index(f"const {name} =")
    return source[start : source.index(";\n", start) + 2]


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


PRELUDE = (
    _const(DOCS, "MD_COLOURS")
    + _const(DOCS, "MD_RUN_FONTS")
    + _const(DOCS, "MD_RUN")
    + _function(DOCS, "mdRunParse")
    + _function(DOCS, "mdRunFormat")
    + _function(BOARD, "wbRunChars")
    + _function(BOARD, "wbRunApply")
)


def _apply(text: str, frm: int, to: int, patch: dict) -> dict:
    return _node(PRELUDE + f"console.log(JSON.stringify(wbRunApply({json.dumps(text)}, {frm}, {to}, {json.dumps(patch)})));")


def test_parse_keeps_only_valid_values_and_formats_in_one_order():
    out = _node(
        PRELUDE
        + "console.log(JSON.stringify([mdRunParse('hl=red ink=blue font=serif size=24'),"
        "mdRunParse('size=9999 font=comic ink=teal'), mdRunFormat({hl:'red', size:24})]));"
    )
    assert out[0] == {"size": 24, "font": "serif", "ink": "blue", "hl": "red"}
    assert out[1] == {}
    assert out[2] == "size=24 hl=red"


def test_a_selection_becomes_a_run_and_keeps_its_words_selected():
    out = _apply("the cat and the dog", 4, 7, {"size": 24})
    assert out["text"] == "the {{size=24|cat}} and the dog"
    assert out["text"][out["from"] : out["to"]] == "cat"


def test_only_the_selected_words_take_the_change():
    out = _apply("{{size=24 ink=red|big red words}}", 26, 31, {"size": 12})
    assert out["text"] == "{{size=24 ink=red|big red }}{{size=12 ink=red|words}}"
    assert out["text"][out["from"] : out["to"]] == "words"


def test_clearing_every_value_takes_the_marks_off():
    out = _apply("a {{size=24|b}} c", 12, 13, {"size": None})
    assert out["text"] == "a b c"


def test_a_value_set_twice_is_not_wrapped_twice():
    first = _apply("plain", 0, 5, {"font": "mono"})
    second = _apply(first["text"], first["from"], first["to"], {"font": "mono"})
    assert second["text"] == first["text"] == "{{font=mono|plain}}"


def test_other_marks_inside_the_selection_stay_and_a_line_break_ends_the_run():
    out = _apply("a **b**\nc", 0, 9, {"ink": "red"})
    assert out["text"] == "{{ink=red|a **b**}}\n{{ink=red|c}}"


def test_a_closing_brace_cannot_be_inside_a_run():
    out = _apply("a } b", 0, 5, {"size": 20})
    assert "}" in out["text"] and out["text"].count("{{") == 2


def test_the_run_is_part_of_the_inline_grammar_and_the_preview_reads_its_words():
    run = re.search(r"const MD_RUN = (/.*?/);", DOCS).group(1)
    for name in ("INLINE_MD", "INLINE_MD_LEGACY"):
        body = re.search(rf"const {name} =\s*(/.*?/g);", NOTES, re.S).group(1)
        assert run[1:-1] in body, f"{name} lost the run alternative"
    assert "mdRunNode(" in _function(NOTES, "appendInlineRun")
    node = _function(DOCS, "mdRunNode")
    assert "style.fontSize" in node and "style.fontFamily" in node
    # The CSP rejects a style attribute: only CSSOM, never setAttribute("style").
    assert 'setAttribute("style"' not in node
    preview = _function((JS / "shell-reminders.js").read_text(encoding="utf-8"), "notePreviewText")
    assert "m[14]" in preview


def test_the_font_table_is_one_source_the_board_builds_from():
    fonts = set(re.findall(r"^\s+(\w+):", re.search(r"const MD_RUN_FONTS = Object\.freeze\(\{(.*?)\}\);", DOCS, re.S).group(1), re.M))
    assert "MD_RUN_FONTS." in MAP and "MD_RUN_FONTS.hand" in BOARD
    assert fonts == {"serif", "mono", "wide", "hand"}


def test_every_run_colour_has_the_classes_the_run_is_drawn_with():
    for colour in re.findall(r'"([a-z]+)"', re.search(r"const MD_COLOURS = \[(.*?)\];", DOCS, re.S).group(1)):
        assert f"mark.text-highlight-{colour}" in CSS and f".text-ink-{colour}" in CSS


def test_the_selection_bar_gets_a_board_only_text_style_control_and_the_format_panel_is_one_press_away():
    fit = _function(BOARD, "wbSelectionBarFit")
    assert "data-board-run" in fit or "boardRun" in fit
    assert "WB_BAR_TEXT" in BOARD and "boardRun" in BOARD
    menu = _function(BOARD, "wbOpenRunMenu")
    for needle in ("wbRunApply(", "swatchPicker(", 'wbFormatOpen("text")', "Size", "Font", "Text colour", "Highlight"):
        assert needle in menu, needle
    # The menu's edits go through the editing surface, so the browser's Undo holds them.
    assert "wbSpliceEditable(" in menu
    assert "wbBarMenuHelp" not in menu
    assert "surface" in EDITOR  # the bar is the editor's; the board only fits it


def test_the_export_draws_runs_as_tspans_with_their_own_attributes():
    export = _function(BOARD, "wbSvgRunLines")
    assert "font-size" in export and "font-family" in export and "fill" in export
    text_branch = BOARD[BOARD.index('} else if (obj.kind === "text") {', BOARD.index("function wbSvgText(")):]
    assert "wbSvgRunLines(" in text_branch[:1800]


def test_a_previews_words_have_no_run_marks_on_the_server_side_either():
    from tessellate.entry.manager import strip_inline_markdown

    assert strip_inline_markdown("a {{size=24 ink=red|big}} **b**") == "a big b"
