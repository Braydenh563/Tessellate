"""The table editor's round trip through Source is byte-exact.

DOCUMENTS_PLAN Phase 3 item 1 and PLAN D4's gate, in one sentence: **a table
edited in Live and then read in Source has to be the markdown a person would
have typed.** Not "equivalent markdown", not "the same table re-printed": the
same bytes, because a markdown file that comes back with its padding rebuilt
every time somebody ticks a cell is a file whose diffs are noise and whose
author no longer wrote it.

The way that promise is kept is in `documents.js`'s own comment: the table
model never prints a table. Every operation returns the smallest
`{from, to, insert}` edits that can express it, so every byte the operation
did not have to touch is still the byte the author typed. This test is the
measurement of that claim rather than a restatement of it, and it measures it
the only honest way: by applying an operation *and its inverse* and comparing
the result to the original string, character for character.

Python cannot run the editor, so the marked region of documents.js
(`DOC-TABLE-BEGIN` to `DOC-TABLE-END`) is executed in node. That region is
pure string work with no DOM and no app globals in it, which is a property
worth keeping and which this test enforces by construction: the day somebody
reaches for `document` in there, this file stops running.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_JS = ROOT / "frontend" / "js" / "documents.js"

#: The marker *lines*, not the bare names: documents.js's own comment above
#: the region says what the markers are for, so the names appear twice in the
#: file and a `find` on the bare name extracts the comment instead of the code.
BEGIN = "// DOC-TABLE-BEGIN"
END = "// DOC-TABLE-END"


def table_model_source() -> str:
    """The bracketed region of documents.js, on its own."""
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    start = text.find(BEGIN)
    end = text.find(END)
    assert start != -1, f"{BEGIN} marker is missing from documents.js"
    assert end > start, f"{END} marker is missing or before {BEGIN}"
    return text[start + len(BEGIN) : end]


#: The shapes a real notebook has in it. Each one is here because it is a way
#: a re-serialising implementation quietly changes a file: an escaped pipe
#: becomes a column break or a double backslash, hand-padded columns get
#: rebuilt, a table written without outer pipes gets them, an indented table
#: is pulled to the margin, and trailing spaces after the last pipe vanish.
SHAPES = {
    "canonical": "| Name | Notes |\n| --- | --- |\n| One | Two |\n| Three | Four |",
    "escaped_pipe": (
        "| Command | What it does |\n"
        "| --- | --- |\n"
        "| `a \\| b` | pipes a into b |\n"
        "| plain | nothing \\| special |"
    ),
    "ragged_widths": "|Name|Notes|\n|---|------------|\n| a |  b |\n|   c|d|",
    "no_outer_pipes": "Name | Notes\n--- | ---\nOne | Two",
    "indented_and_trailing": "  | a | b |   \n  | --- | :---: |\n  | 1 | 2 |  ",
    "aligned": "| a | b | c |\n| :--- | :---: | ---: |\n| 1 | 2 | 3 |",
}

#: The same tables with prose around them, so every offset in the assertions
#: below is a real document offset rather than a table-local one.
PROSE_BEFORE = "# A document\n\nSome words before it.\n\n"
PROSE_AFTER = "\n\nAnd a paragraph after it.\n"


DRIVER = r"""
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
}

const SHAPES = JSON.parse(process.argv[2]);
const BEFORE = JSON.parse(process.argv[3]);
const AFTER = JSON.parse(process.argv[4]);

for (const [shape, table] of Object.entries(SHAPES)) {
  const text = BEFORE + table + AFTER;
  const at = BEFORE.length;

  // 1. Every line puts itself back together exactly.
  for (const line of table.split("\n")) {
    const back = docTableJoinRow(docTableSplitRow(line));
    check(`${shape}/split-join`, back === line, JSON.stringify({ line, back }));
  }

  // 2. The parse finds the whole table and nothing but the table, from any
  //    offset inside it.
  let parsed = null;
  for (let offset = at; offset <= at + table.length; offset += 1) {
    const found = docTableParse(text, offset);
    if (!found) {
      check(`${shape}/parse-at-${offset - at}`, false, "no table at this offset");
      continue;
    }
    if (!parsed) parsed = found;
    check(
      `${shape}/parse-span-${offset - at}`,
      text.slice(found.from, found.to) === table,
      JSON.stringify(text.slice(found.from, found.to))
    );
  }
  if (!parsed) continue;

  // 3. Every cell's span is the cell's own bytes and nobody else's, which is
  //    what the caret rides on: `docTableGo` selects `span.from + lead` to
  //    `span.to - tail` after every Tab, so a span off by one puts the next
  //    keystroke in the neighbouring column.
  //
  //    This replaces three sections that went through a `docTableSetCellEdits`
  //    writer. Nothing in the app ever called it: a cell is edited by typing
  //    into the source line, the way every other character in the document is,
  //    and the only programmatic write the editor makes is the ghost-cell fill
  //    in section 7. Testing a writer no feature used meant the byte-exactness
  //    promise was demonstrated against a path a person could not reach.
  for (let row = 0; row < parsed.rows.length; row += 1) {
    for (let col = 0; col < parsed.rows[row].cells.length; col += 1) {
      const span = docTableCellSpan(parsed, row, col);
      check(`${shape}/cell-span-${row}-${col}`,
        span && text.slice(span.from, span.to) === parsed.rows[row].cells[col],
        span ? JSON.stringify(text.slice(span.from, span.to)) : "no span");
    }
    //: Adjacent spans are separated by exactly the one pipe between them, so
    //: no cell can swallow its neighbour's padding.
    for (let col = 1; col < parsed.rows[row].cells.length; col += 1) {
      const prev = docTableCellSpan(parsed, row, col - 1);
      const here = docTableCellSpan(parsed, row, col);
      check(`${shape}/cell-gap-${row}-${col}`,
        prev && here && text.slice(prev.to, here.from) === "|",
        prev && here ? JSON.stringify(text.slice(prev.to, here.from)) : "no span");
    }
  }

  // 4. The caret lands inside the cell it was sent to, for every cell: the
  //    lead/tail trim `docTableGo` applies must stay within the span.
  for (let row = 0; row < parsed.rows.length; row += 1) {
    for (let col = 0; col < parsed.rows[row].cells.length; col += 1) {
      const span = docTableCellSpan(parsed, row, col);
      const raw = parsed.rows[row].cells[col];
      const lead = (/^[ \t]*/.exec(raw) || [""])[0].length;
      const tail = (/[ \t]*$/.exec(raw) || [""])[0].length;
      const from = span.from + lead;
      const to = Math.max(from, span.to - tail);
      check(`${shape}/caret-inside-${row}-${col}`, from >= span.from && to <= span.to,
        JSON.stringify([span.from, from, to, span.to]));
      check(`${shape}/caret-selects-the-value-${row}-${col}`,
        text.slice(from, to) === raw.trim(), JSON.stringify(text.slice(from, to)));
    }
  }

  // 6. Add a row, remove it again: the original.
  {
    const added = docTableApplyEdits(text, docTableAddRowEdits(parsed, parsed.rows.length - 1));
    const reparsed = docTableParse(added, at);
    check(`${shape}/row-added`, reparsed && reparsed.rows.length === parsed.rows.length + 1,
      reparsed ? String(reparsed.rows.length) : "no table");
    if (reparsed) {
      const back = docTableApplyEdits(added, docTableRemoveRowEdits(reparsed, reparsed.rows.length - 1));
      check(`${shape}/row-round-trip`, back === text, JSON.stringify(back));
    }
  }

  // 7. Add a column, remove it again: the original. Both ends, because the
  //    first column owns the pipe after it and every other column the pipe
  //    before it, and getting that backwards leaves a broken row.
  for (const afterCol of [0, parsed.columns - 1]) {
    const added = docTableApplyEdits(text, docTableAddColumnEdits(parsed, afterCol));
    const reparsed = docTableParse(added, at);
    check(`${shape}/col-added-${afterCol}`, reparsed && reparsed.columns === parsed.columns + 1,
      reparsed ? String(reparsed.columns) : "no table");
    if (!reparsed) continue;
    for (let row = 0; row < reparsed.rows.length; row += 1) {
      //: A body row with no trailing pipe cannot hold a blank final cell:
      //: GFM drops it, so the column is left for the renderer to pad and for
      //: the first write to materialise. Every other row grows by one.
      const ghost =
        row !== 0 && row !== parsed.delim && afterCol === parsed.columns - 1 && !parsed.rows[row].trail;
      check(
        `${shape}/col-added-cells-${afterCol}-${row}`,
        reparsed.rows[row].cells.length === parsed.rows[row].cells.length + (ghost ? 0 : 1),
        String(reparsed.rows[row].cells.length)
      );
      if (!ghost) continue;
      //: The ghost cell is made real by `docTableFillRowEdits`, which is what
      //: `docTableGo` calls when Tab sends the caret into a cell the text does
      //: not have yet. Afterwards the row holds it for real, blank, and the
      //: table is still the same width.
      const written = docTableApplyEdits(added, docTableFillRowEdits(reparsed, row, parsed.columns));
      const again = docTableParse(written, at);
      check(`${shape}/ghost-cell-filled-${row}`,
        !!again && again.rows[row].cells.length === parsed.columns + 1,
        again ? String(again.rows[row].cells.length) : "no table");
      check(`${shape}/ghost-cell-filled-blank-${row}`,
        !!again && again.rows[row].cells[parsed.columns].trim() === "",
        again ? JSON.stringify(again.rows[row].cells[parsed.columns]) : "no table");
      check(`${shape}/ghost-cell-filled-width-${row}`, !!again && again.columns === parsed.columns + 1,
        again ? String(again.columns) : "no table");
      //: And filling a cell the row already has is not an edit, so Tab into an
      //: ordinary cell cannot rewrite the row on the way.
      check(`${shape}/ghost-cell-fill-is-idempotent-${row}`,
        !!again && docTableFillRowEdits(again, row, parsed.columns).length === 0,
        "filling an existing cell produced an edit");
    }
    const back = docTableApplyEdits(added, docTableRemoveColumnEdits(reparsed, afterCol + 1));
    check(`${shape}/col-round-trip-${afterCol}`, back === text, JSON.stringify(back));
  }

  // 7b. The same from the other side: a column inserted *before* one, then
  //     removed, is the original. The first column is the case that matters,
  //     because it owns the pipe on its right where every other column owns
  //     the one on its left.
  for (const col of [0, parsed.columns - 1]) {
    const added = docTableApplyEdits(text, docTableAddColumnEdits(parsed, col, true));
    const reparsed = docTableParse(added, at);
    check(`${shape}/col-before-added-${col}`, reparsed && reparsed.columns === parsed.columns + 1,
      reparsed ? String(reparsed.columns) : "no table");
    if (!reparsed) continue;
    check(`${shape}/col-before-named-${col}`, reparsed.rows[0].cells[col].trim() === "Column",
      JSON.stringify(reparsed.rows[0].cells[col]));
    const back = docTableApplyEdits(added, docTableRemoveColumnEdits(reparsed, col));
    //: The one documented exception, and it is markdown's rather than the
    //: editor's: a row with no outer pipes cannot hold a blank *first* cell,
    //: because GFM reads the leading spaces as indentation and strips the
    //: optional leading pipe. Such a table gains a leading pipe when a column
    //: goes in front of it and keeps that pipe when the column is removed
    //: again. Every other byte, including the padding of every other cell, is
    //: the author's.
    const gained = docTableApplyEdits(
      text,
      parsed.rows
        .filter((row) => !row.lead)
        .map((row) => ({ from: row.from + row.indent.length, to: row.from + row.indent.length, insert: "|" }))
    );
    const want = col === 0 ? gained : text;
    check(`${shape}/col-before-round-trip-${col}`, back === want, JSON.stringify(back));
  }

  // 8. Alignment is one delimiter cell, and setting it to what it already is
  //    is not an edit.
  for (let col = 0; col < parsed.columns; col += 1) {
    const already = docTableAlignEdits(parsed, col, parsed.aligns[col]);
    check(`${shape}/align-same-${col}`, already.length === 0, JSON.stringify(already));
    const right = docTableApplyEdits(text, docTableAlignEdits(parsed, col, "right"));
    const reparsed = docTableParse(right, at);
    check(`${shape}/align-right-${col}`, reparsed && reparsed.aligns[col] === "right",
      reparsed ? String(reparsed.aligns[col]) : "no table");
    if (!reparsed) continue;
    const back = docTableApplyEdits(right, docTableAlignEdits(reparsed, col, parsed.aligns[col]));
    check(`${shape}/align-round-trip-${col}`, back === text, JSON.stringify(back));
  }

  // 9. Tab walks the cells and steps over the delimiter row.
  {
    const last = parsed.rows.length - 1;
    const end = docTableStepCell(parsed, last, parsed.rows[last].cells.length - 1, 1);
    check(`${shape}/tab-past-the-end`, end === null, JSON.stringify(end));
    const fromHeader = docTableStepCell(parsed, 0, parsed.columns - 1, 1);
    check(`${shape}/tab-skips-the-delimiter`, fromHeader && fromHeader.row === 2,
      JSON.stringify(fromHeader));
  }
}

// A paragraph that merely contains a pipe is not a table, and a table sitting
// under one is still found: the run of pipe-bearing lines around the caret is
// wider than the table in both of these.
{
  const text = "one | two is a choice\n\n| a | b |\n| --- | --- |\n| 1 | 2 |";
  check("prose/not-a-table", docTableParse(text, 3) === null, "a paragraph parsed as a table");
  const found = docTableParse(text, text.indexOf("| 1"));
  check("prose/table-under-prose", !!found && found.columns === 2, found ? String(found.columns) : "none");
}
{
  const text = "run | of | prose\n| a | b |\n| --- | --- |\n| 1 | 2 |";
  const found = docTableParse(text, text.indexOf("| 1"));
  check("prose/header-not-the-run-start", !!found && text.slice(found.from, found.to) ===
    "| a | b |\n| --- | --- |\n| 1 | 2 |", found ? text.slice(found.from, found.to) : "none");
}

process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def table_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("doctable") / "run.js"
    script.write_text(table_model_source() + DRIVER, encoding="utf-8")
    out = subprocess.run(
        [node, str(script), json.dumps(SHAPES), json.dumps(PROSE_BEFORE), json.dumps(PROSE_AFTER)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_model_runs_without_a_browser(table_checks: list[dict]) -> None:
    """No DOM, no app globals: the region is pure string work."""
    assert len(table_checks) > 400, "the driver did not reach the end of the shapes"


def test_every_table_operation_round_trips_byte_for_byte(table_checks: list[dict]) -> None:
    failed = [c for c in table_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


#: INBOX 425 i: the transforms behind Enter, the arrows and a spreadsheet
#: paste in the Live table. Each is pure string work in the same region, so
#: it runs in node beside the round-trip driver above.
TRANSFORMS = r"""
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
}
const T = "| Name | Kind |\n| --- | --- |\n| a1 | b1 |\n| a2 | b2 |";
const PRE = "Words.\n\n";
const text = PRE + T + "\n\nAfter.";
const table = docTableParse(text, PRE.length);

// The row a vertical step lands on steps over the delimiter, and is null
// past either edge.
check("step/header-down", docTableStepRow(table, 0, 1) === 2, docTableStepRow(table, 0, 1));
check("step/body-up", docTableStepRow(table, 2, -1) === 0, docTableStepRow(table, 2, -1));
check("step/last-down", docTableStepRow(table, 3, 1) === null, docTableStepRow(table, 3, 1));
check("step/header-up", docTableStepRow(table, 0, -1) === null, docTableStepRow(table, 0, -1));

// A spreadsheet's clipboard: rows, tabs, a trailing newline that is not a
// row, CRLF, a pipe escaped once and an escaped pipe left alone.
check("grid/none-without-a-tab", docTableGridFromText("plain words\nmore") === null, "parsed");
const grid = docTableGridFromText("x1\ty1\r\nx|2\ty\\|2\n");
check("grid/shape", !!grid && grid.length === 2 && grid[0].length === 2, JSON.stringify(grid));
check("grid/escaped", !!grid && grid[1][0] === "x\\|2" && grid[1][1] === "y\\|2", JSON.stringify(grid));

// A new table from a grid.
check("from-grid", docTableFromGrid([["H1", "H2"], ["v1", ""]]) ===
  "| H1 | H2 |\n| --- | --- |\n| v1 |  |", JSON.stringify(docTableFromGrid([["H1", "H2"], ["v1", ""]])));
const made = docTableParse(docTableFromGrid([["H1", "H2"], ["v1", "v2"]]), 0);
check("from-grid/parses", !!made && made.columns === 2 && made.rows.length === 3, made ? made.rows.length : "none");

// Setting a cell keeps its padding; a blank cell is written ` text `.
const padded = "|  a  | b |\n| --- | --- |\n|  | x |";
const pt = docTableParse(padded, 0);
const set = docTableApplyEdits(padded, docTableSetCellEdits(pt, [
  { row: 0, col: 0, text: "Z" }, { row: 2, col: 0, text: "new" }]));
check("set/padding-kept", set === "|  Z  | b |\n| --- | --- |\n| new | x |", JSON.stringify(set));

// Paste into a cell: fills right and down, one undo-able edit over the table.
const p1 = docTablePasteEdits(text, table, 2, 1, [["P", "Q"], ["R", "S"], ["T", "U"]]);
const after1 = docTableApplyEdits(text, [p1.edit]);
const t1 = docTableParse(after1, PRE.length);
check("paste/prose-untouched", after1.startsWith(PRE) && after1.endsWith("\n\nAfter."), JSON.stringify(after1));
check("paste/grows", !!t1 && t1.columns === 3 && t1.rows.length === 5, t1 ? `${t1.columns}x${t1.rows.length}` : "none");
check("paste/cells", !!t1 && t1.rows[2].cells[1].trim() === "P" && t1.rows[2].cells[2].trim() === "Q" &&
  t1.rows[4].cells[1].trim() === "T" && t1.rows[4].cells[2].trim() === "U" && t1.rows[2].cells[0].trim() === "a1",
  t1 ? JSON.stringify(t1.rows.map((r) => r.cells)) : "none");
check("paste/caret-cell", p1.row === 4 && p1.col === 2, JSON.stringify([p1.row, p1.col]));
check("paste/one-edit-over-the-table", p1.edit.from === table.from && p1.edit.to === table.to, JSON.stringify(p1.edit));

// A paste inside the table's shape changes only the cells it names.
const p2 = docTablePasteEdits(text, table, 3, 0, [["only", "these"]]);
const after2 = docTableApplyEdits(text, [p2.edit]);
check("paste/in-place", after2 === text.replace("| a2 | b2 |", "| only | these |"), JSON.stringify(after2));

// On the delimiter, the paste starts on the first body row.
const p3 = docTablePasteEdits(text, table, 1, 0, [["d", "e"]]);
const t3 = docTableParse(docTableApplyEdits(text, [p3.edit]), PRE.length);
check("paste/delimiter-to-body", !!t3 && t3.rows[2].cells[0].trim() === "d" && t3.rows[1].cells[0].includes("-"),
  t3 ? JSON.stringify(t3.rows.map((r) => r.cells)) : "none");

// The way out below (Ctrl+Enter, Enter on an empty last row): the caret lands
// on the line under the table, or on a fresh one when the table ends the text.
const exitText = "| a | b |\n| --- | --- |\n| 1 | 2 |\n|  |  |";
const exitTable = docTableParse(exitText, 0);
const exitEnd = docTableExitEdit(exitTable, exitText, true);
const exitDone = docTableApplyEdits(exitText, exitEnd.changes);
check("exit/empty-row-dropped", exitDone === "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n" && exitDone.length === exitEnd.anchor,
  JSON.stringify([exitDone, exitEnd.anchor]));
const exitMid = "| a |\n| --- |\n| 1 |\nafter";
const exitMidEdit = docTableExitEdit(docTableParse(exitMid, 0), exitMid, false);
check("exit/blank-line-before-text", docTableApplyEdits(exitMid, exitMidEdit.changes) === "| a |\n| --- |\n| 1 |\n\nafter" && exitMidEdit.anchor === 21, JSON.stringify(exitMidEdit));
const exitBlank = "| a |\n| --- |\n| 1 |\n\nafter";
const exitBlankEdit = docTableExitEdit(docTableParse(exitBlank, 0), exitBlank, false);
check("exit/existing-blank-line-reused", exitBlankEdit.changes.length === 0 && exitBlank.slice(exitBlankEdit.anchor) === "after", JSON.stringify(exitBlankEdit));
const exitKeep = docTableExitEdit(docTableParse("| a |\n| --- |\n| 1 |", 0), "| a |\n| --- |\n| 1 |", false);
check("exit/end-of-document-adds-blank-line", exitKeep.anchor === 21 && exitKeep.changes[0].insert === "\n\n", JSON.stringify(exitKeep));

process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def transform_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("doctablex") / "run.js"
    script.write_text(table_model_source() + TRANSFORMS, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_live_table_transforms_do_what_the_gestures_need(transform_checks: list[dict]) -> None:
    """Enter and the arrows step over the delimiter, a spreadsheet paste fills
    cells (growing the table) in one edit, and a pasted grid becomes a table."""
    assert len(transform_checks) >= 17
    failed = [c for c in transform_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed)
