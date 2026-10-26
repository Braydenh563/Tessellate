"""Paste options and Paste special in the document editor (docpaste-1026).

The pure half (reading a clipboard as a quote, a checklist, a code block, a
table or a link) runs in node; the wiring is checked as text, because the suite
cannot see the DOM (the Playwright run is `scratchpad/ui-sweeps/docpaste.js`)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROSE = (ROOT / "frontend/js/documents-prose.js").read_text(encoding="utf-8")
DOCUMENTS = (ROOT / "frontend/js/documents.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend/index.html").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _fn(name: str) -> str:
    start = DOCUMENTS.index(f"function {name}(")
    return DOCUMENTS[start : DOCUMENTS.index("\n}\n", start) + 3]


def _pure() -> str:
    body = PROSE[PROSE.index("// DOC-PASTE-PURE-START") : PROSE.index("// DOC-PASTE-PURE-END")]
    return _fn("docTableEscapeCell") + _fn("docTableFromGrid") + body


def _run(expr: str):
    script = _pure() + f"\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


def _t(mode: str, text: str, doc: str = "", sel: tuple[int, int] = (0, 0)):
    return _run(f"docPasteTransform({json.dumps(mode)}, {json.dumps(text)}, {json.dumps(doc)}, {sel[0]}, {sel[1]})")


@needs_node
def test_a_web_address_over_selected_words_is_a_link_and_bare_gets_its_host():
    assert _t("link", "https://example.com/a", "see docs here", (4, 8)) == "[docs](https://example.com/a)"
    assert _t("link", " https://www.example.com/a ") == "[example.com](https://www.example.com/a)"
    assert _t("link", "not a url") == ""
    assert _t("link", "javascript:alert(1)") == ""


@needs_node
def test_a_quote_and_a_checklist_take_one_line_per_item_and_drop_old_bullets():
    assert _t("quote", "one\n\ntwo") == "> one\n> two"
    assert _t("checklist", "- milk\n2. eggs\n[x] bread\n\nplain") == "- [ ] milk\n- [ ] eggs\n- [ ] bread\n- [ ] plain"


@needs_node
def test_a_code_block_guesses_the_language_and_outgrows_backticks_inside():
    assert _t("code", "def f():\n    return 1\n") == "```python\ndef f():\n    return 1\n```"
    assert _t("code", '{"a": 1}') == '```json\n{"a": 1}\n```'
    assert _t("code", "nothing special here").startswith("```\n")
    assert _t("code", "```js\nx\n```").startswith("````")


@needs_node
def test_a_spreadsheet_or_csv_becomes_a_table_with_escaped_pipes_and_block_spacing():
    assert _t("table", "a\tb\n1\t2\n") == "| a | b |\n| --- | --- |\n| 1 | 2 |"
    assert _t("table", 'n,note\n1,"x, y"\n2,"say ""hi"""') == "| n | note |\n| --- | --- |\n| 1 | x, y |\n| 2 | say \"hi\" |"
    assert _t("table", "just words") == ""
    assert _t("table", "a,b\n1") == ""  # ragged CSV is prose, not a table
    # Text on the line before it: a blank line first, and one after.
    assert _t("table", "a\tb\n1\t2", "intro text", (10, 10)).startswith("\n\n| a | b |")
    # A line under it needs one line break; text after it on the same line, a blank line.
    assert _t("table", "a\tb\n1\t2", "x\nafter", (1, 1)).endswith("| 1 | 2 |\n")
    assert _t("table", "a\tb\n1\t2", "x tail", (1, 1)).endswith("| 1 | 2 |\n\n")


@needs_node
def test_plain_text_and_markdown_source_differ_in_what_they_clean():
    assert _t("plain", "a  b  \r\nc\r\n\r\n") == "a  b\nc"
    assert _t("source", "a  \r\n**b**\r\n") == "a  \n**b**\n"


@needs_node
def test_match_surrounding_carries_a_quote_or_list_prefix_to_later_lines():
    assert _t("match", "one\ntwo", "> start ", (8, 8)) == "one\n> two"
    assert _t("match", "one\ntwo", "- item ", (7, 7)) == "one\n  two"
    assert _t("match", "one\ntwo", "plain ", (6, 6)) == "one\ntwo"


def test_the_paste_chain_is_table_then_smart_then_rich():
    assert "docTablePasteEvent(event, view) || docSmartPasteEvent(event, view) || docRichPasteEvent(event, view)" in DOCUMENTS


def test_ctrl_shift_v_still_beats_the_smart_paste_and_a_linewise_paste_is_left_alone():
    body = PROSE[PROSE.index("function docSmartPasteEvent") :]
    assert "docPastePlain || docPasteIsLinewise(plain)" in body.split("\n}\n")[0]


def test_a_chip_choice_is_one_undo_step_and_refuses_a_range_that_moved():
    body = PROSE[PROSE.index("function docPasteChoose") : PROSE.index("function docPasteChipMenu")]
    assert "docUndoBreak()" in body and "sliceString(chip.from, chip.to) !== now.text" in body


def test_the_chip_uses_the_pointer_menu_recipe_and_is_keyboard_reachable():
    assert "openMenuAtPoint(items, \"Paste options\"" in PROSE
    keys = PROSE[PROSE.index("function docPasteChipKey") : PROSE.index("function docPasteOffer(")]
    assert '"Control"' in keys and "docPasteChipClose()" in keys
    assert "chip.onKeyUp" in PROSE and 'event.key === "Control" && chip.ctrl' in PROSE


def test_the_rich_and_table_pastes_offer_the_chip():
    assert "docPasteOfferRich(view" in _fn("docRichPasteEvent")
    assert "docPasteOfferTable(view" in _fn("docTablePasteEvent")


def test_paste_special_is_a_menu_row_and_palette_commands_all_prose_free_of_code_files():
    assert 'id="doc-paste-special"' in INDEX
    assert '$("doc-paste-special")?.addEventListener("click"' in DOCUMENTS
    for mode in ("plain", "code", "quote", "table", "link", "checklist"):
        assert f'docPasteSpecial("{mode}")' in DOCUMENTS
    assert "docPasteSpecialMenu()" in DOCUMENTS
    spec = re.findall(r'\["(\w+)", "Paste', PROSE)
    assert spec == ["plain", "source", "code", "quote", "table", "link", "checklist"]


def test_paste_special_works_without_clipboard_permission_by_arming_the_next_paste():
    body = PROSE[PROSE.index("async function docPasteSpecial(") :]
    assert "navigator.clipboard.readText()" in body and "docPasteArmed = mode" in body
