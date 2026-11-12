"""A Markdown (pipe) table pasted onto a board becomes a table (LEDGER L273 row;
WHITEBOARD_PLAN section 12). `pasteGrid.pipe` is in the shared paste core, so the
document editor's Paste special table reads it too."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
PROSE = (ROOT / "frontend" / "js" / "documents-prose.js").read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end)]


PURE = _between(PROSE, "// PASTE-CORE-START", "// PASTE-CORE-END") + _between(COMMANDS, "// WB-PASTE-PURE-START", "// WB-PASTE-PURE-END")


def _js(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", PURE + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


MD = "| Name | Owner |\n| --- | :-: |\n| Plan | Ann |\n| Ship | Bo |\n"


def test_a_pipe_table_becomes_rows_without_its_rule():
    assert _js(f"pasteGrid({json.dumps(MD)})") == [["Name", "Owner"], ["Plan", "Ann"], ["Ship", "Bo"]]


def test_a_pipe_table_is_the_default_reading_of_the_paste():
    plan = _js(f"wbPastePlan({json.dumps(MD)})")
    assert plan["kind"] == "table" and plan["grid"][0] == ["Name", "Owner"]
    assert _js(f"wbPasteVariants({json.dumps(MD)})")[0] == "table"


def test_pipes_without_outer_bars_escapes_and_short_rows():
    text = "a | b | c\n--- | --- | ---\nx \\| y | 2\n"
    assert _js(f"pasteGrid({json.dumps(text)})") == [["a", "b", "c"], ["x | y", "2", ""]]


@pytest.mark.parametrize(
    "text",
    [
        "| just | a line |",
        "| a | b |\n| c | d |",
        "| a | b |\n| --- |\n| c | d |",
        "- one | two\n- three | four",
        "plain words\nmore words",
    ],
)
def test_text_that_is_not_a_pipe_table_is_left_alone(text):
    assert _js(f"pasteGrid.pipe({json.dumps(text)})") is None


def test_a_table_item_from_a_pipe_paste_has_a_header_and_the_cells():
    item = _js(f"wbPasteTableItem(pasteGrid({json.dumps(MD)}), 0, 0)")
    assert item["payload"]["kind"] == "table"
    assert item["payload"]["data"] == {"cells": [["Name", "Owner"], ["Plan", "Ann"], ["Ship", "Bo"]], "header": True}


def test_tabs_and_commas_still_read_as_before():
    tabs, commas = json.dumps("a\tb\nc\td"), json.dumps("a,b\nc,d")
    assert _js(f"pasteGrid({tabs})") == [["a", "b"], ["c", "d"]]
    assert _js(f"pasteGrid({commas})") == [["a", "b"], ["c", "d"]]
