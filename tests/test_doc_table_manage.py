"""Managing a Live table: move, sort and select by row and column (INBOX 904 B23).

The owner: "the tables in the live view ... should have more management
capability, like lines on the edges and rows and columns on the outside etc
to select whole rows or columns, or to add new rows or columns or even
dragging icons to drag and rearrange columns and rows". The model half is
pure string work like the rest of the table region of documents.js, run here
in node: every operation is a list of edits, applied to the text and compared
to the table a person would have written by hand. The drawn half (the edge
grips, the right-click menu, the drag) is
`scratchpad/ui-sweeps/tablemanage1018.js`.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests.test_doc_tables import table_model_source

DRIVER = r"""
const out = [];
const eq = (name, got, want) => out.push({ name, ok: JSON.stringify(got) === JSON.stringify(want), got });
const T = "| Name | Qty | Note |\n| :--- | ---: | --- |\n| pear | 10 | green |\n| apple | 2 | red |\n| fig | 33 | purple |";
const BEFORE = "Intro\n\n";
const text = BEFORE + T + "\n\nAfter\n";
const table = docTableParse(text, BEFORE.length + 3);
const apply = (edits) => docTableApplyEdits(text, edits).slice(BEFORE.length).split("\n\n")[0];

// Rows: the body rows swap whole lines, the header and the delimiter never move.
eq("row down", apply(docTableMoveRowEdits(table, 2, 1)).split("\n").slice(2), ["| apple | 2 | red |", "| pear | 10 | green |", "| fig | 33 | purple |"]);
eq("row up", apply(docTableMoveRowEdits(table, 4, -1)).split("\n").slice(2), ["| pear | 10 | green |", "| fig | 33 | purple |", "| apple | 2 | red |"]);
eq("first row cannot go up", docTableMoveRowEdits(table, 2, -1), []);
eq("last row cannot go down", docTableMoveRowEdits(table, 4, 1), []);
eq("header does not move", docTableMoveRowEdits(table, 0, 1), []);
eq("delimiter does not move", docTableMoveRowEdits(table, 1, 1), []);
eq("row move and back is byte-exact", docTableApplyEdits(docTableApplyEdits(text, docTableMoveRowEdits(table, 2, 1)), docTableMoveRowEdits(docTableParse(docTableApplyEdits(text, docTableMoveRowEdits(table, 2, 1)), BEFORE.length + 3), 3, -1)), text);

// Columns: every row's cells swap, and the alignment marker goes with its column.
eq("column right", apply(docTableMoveColumnEdits(table, 0, 1)).split("\n"), ["| Qty | Name | Note |", "| ---: | :--- | --- |", "| 10 | pear | green |", "| 2 | apple | red |", "| 33 | fig | purple |"].map((l) => l));
eq("column left", apply(docTableMoveColumnEdits(table, 2, -1)).split("\n")[0], "| Name | Note | Qty |");
eq("first column cannot go left", docTableMoveColumnEdits(table, 0, -1), []);
eq("last column cannot go right", docTableMoveColumnEdits(table, 2, 1), []);
const moved = docTableApplyEdits(text, docTableMoveColumnEdits(table, 1, 1));
eq("column move and back is byte-exact", docTableApplyEdits(moved, docTableMoveColumnEdits(docTableParse(moved, BEFORE.length + 3), 2, -1)), text);
const ragged = "| a | b | c |\n| --- | --- | --- |\n| 1 | 2 |\n| x | y | z |";
const rt = docTableParse(ragged, 2);
eq("column move on a ragged row fills the missing cell", docTableApplyEdits(ragged, docTableMoveColumnEdits(rt, 1, 1)).split("\n")[2].replace(/\s+/g, " "), "| 1 | | 2 |");

// Sort: the body rows by one column, numbers as numbers, stable, header kept.
eq("sort by name", apply(docTableSortEdits(table, 0, false)).split("\n").slice(2).map((l) => l.split("|")[1].trim()), ["apple", "fig", "pear"]);
eq("sort by qty descending is numeric", apply(docTableSortEdits(table, 1, true)).split("\n").slice(2).map((l) => l.split("|")[2].trim()), ["33", "10", "2"]);
eq("sorting a sorted table is no edit", docTableSortEdits(docTableParse(docTableApplyEdits(text, docTableSortEdits(table, 0, false)), BEFORE.length + 3), 0, false), []);
eq("header and delimiter survive a sort", apply(docTableSortEdits(table, 0, true)).split("\n").slice(0, 2), ["| Name | Qty | Note |", "| :--- | ---: | --- |"]);

// Selection: the ranges a row, a column or the table is.
const slice = (r) => r.map((x) => text.slice(x.from, x.to).trim());
eq("select row", slice(docTableSelectRanges(table, "row", 3)), ["apple | 2 | red"]);
eq("select column skips the delimiter", slice(docTableSelectRanges(table, "column", 1)), ["Qty", "10", "2", "33"]);
eq("select column ranges are the cell's words", docTableSelectRanges(table, "column", 0).every((x) => x.from <= x.to), true);
eq("select table", slice(docTableSelectRanges(table, "table", 0)).length, 1);
eq("select out of range", docTableSelectRanges(table, "column", 9), []);

process.stdout.write(JSON.stringify(out));
"""


def test_move_sort_and_select_are_exact(tmp_path) -> None:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path / "manage.js"
    script.write_text(table_model_source() + DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    results = json.loads(out.stdout)
    failed = [r for r in results if not r["ok"]]
    assert not failed, failed
    assert len(results) >= 20
