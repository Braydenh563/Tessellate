"""The csv and tsv grid (L328, decision D42): the pure model of `documents-csvgrid.js`, run in node.

A cell edit is a change to the editor's own text, so the model must rewrite only the cell's own characters, quote
what needs it and keep every other byte (CRLF, a file's own quoting, a last line with no break). The browser half
(focus, keys, one undo step) is measured by driving the app.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "documents-csvgrid.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _model_source() -> str:
    return JS.split("// DOC-CSVGRID-BEGIN", 1)[1].split("// DOC-CSVGRID-END", 1)[0]


def _run(cases: list[dict]) -> list:
    script = (
        _model_source()
        + """
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = cases.map((c) => {
  const model = parse(c.text, c.delim || ",");
  if (c.op === "parse") return { rows: model.rows.map((r) => r.cells.map((x) => x.text)), eol: model.eol };
  if (c.op === "title") return delimiterOf(c.text, c.title);
  if (c.op === "order") return viewOrder(model, c.header, c.sort, c.filters);
  if (c.op === "sortFile") return applyChanges(c.text, sortFile(model, c.text, c.header, c.sort));
  if (c.op === "paste") return applyChanges(c.text, pasteBlock(model, c.targets, c.c, clipRows(c.clip)));
  if (c.op === "clip") return clipRows(c.text);
  const args = c.args || [];
  return applyChanges(c.text, ops[c.op](model, ...args));
});
process.stdout.write(JSON.stringify(out));
"""
    )
    done = subprocess.run(["node", "-e", script], input=json.dumps(cases), capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_parse_reads_quoted_fields_and_endings():
    got = _run(
        [
            {"op": "parse", "text": 'a,"b,c",d\r\n"x ""y""",\r\n"two\nlines",z'},
            {"op": "parse", "text": "a\tb\n1\t2\n", "delim": "\t"},
            {"op": "parse", "text": ""},
            {"op": "parse", "text": "﻿id,name\n1,Ann"},
        ]
    )
    assert got[0] == {"rows": [["a", "b,c", "d"], ['x "y"', ""], ["two\nlines", "z"]], "eol": "\r\n"}
    assert got[1]["rows"] == [["a", "b"], ["1", "2"]]
    assert got[2]["rows"] == []
    assert got[3]["rows"] == [["id", "name"], ["1", "Ann"]]


def test_delimiter_follows_the_title_then_the_first_line():
    got = _run(
        [
            {"op": "title", "text": "a,b", "title": "x.tsv"},
            {"op": "title", "text": "a\tb", "title": "x.csv"},
            {"op": "title", "text": "a,b\tc", "title": "x.csv"},
        ]
    )
    assert got == ["\t", "\t", ","]


def test_set_cell_quotes_only_what_needs_it_and_keeps_the_rest():
    text = 'a,b,c\r\n1,"x, y",3\r\n'
    cases = [
        {"op": "setCell", "text": text, "args": [1, 0, "has,comma"]},
        {"op": "setCell", "text": text, "args": [1, 1, "plain"]},
        {"op": "setCell", "text": text, "args": [0, 2, 'say "hi"']},
        {"op": "setCell", "text": text, "args": [0, 0, "two\nlines"]},
        {"op": "setCell", "text": "a,b\n1", "args": [1, 1, "new"]},
        {"op": "setCell", "text": "only\nx", "args": [0, 0, ""]},
        {"op": "setCell", "text": "a\tb\n", "delim": "\t", "args": [0, 1, "t\tab"]},
    ]
    got = _run(cases)
    assert got[0] == 'a,b,c\r\n"has,comma","x, y",3\r\n'
    assert got[1] == 'a,b,c\r\n1,plain,3\r\n'
    assert got[2] == 'a,b,"say ""hi"""\r\n1,"x, y",3\r\n'
    assert got[3] == 'a,b,c\r\n'.replace("a,b,c", '"two\nlines",b,c') + '1,"x, y",3\r\n'
    assert got[4] == "a,b\n1,new"
    assert got[5] == '""\nx'
    assert got[6] == 'a\t"t\tab"\n'


def test_rows_add_and_delete_without_touching_the_others():
    text = "h1,h2\r\n1,2\r\n3,4"
    got = _run(
        [
            {"op": "addRow", "text": text, "args": [0, True]},
            {"op": "addRow", "text": text, "args": [2, True]},
            {"op": "addRow", "text": text, "args": [1, False]},
            {"op": "deleteRow", "text": text, "args": [1]},
            {"op": "deleteRow", "text": text, "args": [2]},
            {"op": "deleteRow", "text": "only", "args": [0]},
        ]
    )
    assert got[0] == "h1,h2\r\n,\r\n1,2\r\n3,4"
    assert got[1] == "h1,h2\r\n1,2\r\n3,4\r\n,"
    assert got[2] == "h1,h2\r\n,\r\n1,2\r\n3,4"
    assert got[3] == "h1,h2\r\n3,4"
    assert got[4] == "h1,h2\r\n1,2"
    assert got[5] == ""


def test_columns_add_and_delete_across_every_row():
    text = 'a,b,c\n1,"x,y",3\n4,5\n'
    got = _run(
        [
            {"op": "addColumn", "text": text, "args": [1]},
            {"op": "addColumn", "text": text, "args": [3]},
            {"op": "deleteColumn", "text": text, "args": [0]},
            {"op": "deleteColumn", "text": text, "args": [1]},
            {"op": "deleteColumn", "text": text, "args": [2]},
            {"op": "deleteColumn", "text": "a\nb", "args": [0]},
        ]
    )
    assert got[0] == 'a,,b,c\n1,,"x,y",3\n4,,5\n'
    assert got[1] == "a,b,c,\n1,\"x,y\",3,\n4,5\n"
    assert got[2] == 'b,c\n"x,y",3\n5\n'
    assert got[3] == "a,c\n1,3\n4\n"
    assert got[4] == 'a,b\n1,"x,y"\n4,5\n'
    assert got[5] == "\n"


def test_the_grid_is_wired_lazily_with_one_undo_step_and_help():
    lazy = (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'docCsvGrid: ["/css/doc-csv-grid-lazy.css", "/js/documents-csvgrid.js"]' in lazy
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="doc-csv-grid"' in html and 'data-click-proxy="doc-csv-grid"' in html
    documents = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    assert 'ensureModule("docCsvGrid")' in documents
    #: One transaction per edit, never a second copy of the file.
    assert "docCmView.dispatch({ changes" in JS and "docViewState.csvGrid =" in JS
    assert "innerHTML" not in JS


def test_a_cell_is_a_touch_target_by_its_height_not_its_min_height():
    """L-documents-40: a table cell ignores `min-height`, so the coarse-pointer rule measured 27px at 390. The height is the
    floor on a cell; measured 44 x 44 for cells, the row number and the four bar buttons after the fix."""
    css = (ROOT / "frontend" / "css" / "doc-csv-grid-lazy.css").read_text(encoding="utf-8")
    coarse = css.split("@media (pointer: coarse)", 1)[1]
    assert "block-size: var(--target-min)" in coarse and "min-block-size" not in coarse


TEXT = "name,n,city\r\ndelta,10,Oslo\r\nalpha,2,Rome\r\ncharlie,33,Oslo\r\nbravo,,Paris"


def test_the_view_sorts_and_filters_without_touching_the_file():
    """L-documents-39: a view order is a list of file row indices; the header row stays on top, blanks sort last."""
    got = _run(
        [
            {"op": "order", "text": TEXT, "header": True, "sort": None, "filters": {}},
            {"op": "order", "text": TEXT, "header": True, "sort": {"c": 1, "dir": 1}, "filters": {}},
            {"op": "order", "text": TEXT, "header": True, "sort": {"c": 1, "dir": -1}, "filters": {}},
            {"op": "order", "text": TEXT, "header": True, "sort": None, "filters": {"2": "OSL"}},
            {"op": "order", "text": TEXT, "header": True, "sort": {"c": 0, "dir": -1}, "filters": {"2": "oslo", "0": "c"}},
            {"op": "order", "text": TEXT, "header": False, "sort": {"c": 0, "dir": 1}, "filters": {}},
            {"op": "order", "text": "", "header": True, "sort": None, "filters": {}},
        ]
    )
    assert got[0] == [0, 1, 2, 3, 4]
    assert got[1] == [0, 2, 1, 3, 4]  # 2, 10, 33 by value (not "10" before "2"), the blank last
    assert got[2] == [0, 3, 1, 2, 4]  # descending keeps the blank last
    assert got[3] == [0, 1, 3]
    assert got[4] == [0, 3]
    assert got[5] == [2, 4, 3, 1, 0]  # no header: every row sorts, the first line too
    assert got[6] == []


def test_sort_the_file_rewrites_only_the_row_order():
    got = _run(
        [
            {"op": "sortFile", "text": TEXT, "header": True, "sort": {"c": 0, "dir": 1}},
            {"op": "sortFile", "text": TEXT, "header": True, "sort": {"c": 1, "dir": -1}},
            {"op": "sortFile", "text": "a,1\nb,2\n", "header": False, "sort": {"c": 0, "dir": 1}},
            {"op": "sortFile", "text": '"x, y",2\n"a ""q""",1\n', "header": False, "sort": {"c": 1, "dir": 1}},
        ]
    )
    assert got[0] == "name,n,city\r\nalpha,2,Rome\r\nbravo,,Paris\r\ncharlie,33,Oslo\r\ndelta,10,Oslo"
    assert got[1] == "name,n,city\r\ncharlie,33,Oslo\r\ndelta,10,Oslo\r\nalpha,2,Rome\r\nbravo,,Paris"
    assert got[2] == "a,1\nb,2\n"  # already in order: the file is not rewritten
    assert got[3] == '"a ""q""",1\n"x, y",2\n'  # quoted rows move whole, with their own quoting


def test_pasting_a_block_overwrites_grows_rows_and_columns_and_keeps_the_rest():
    text = "h1,h2,h3\n1,2,3\n4,5"
    got = _run(
        [
            {"op": "clip", "text": "a\tb\r\nc\td\r\n"},
            {"op": "clip", "text": '"x\ty"\t"l1\nl2"\n'},
            # 3x2 at row 1, column 1: rows 1 and 2 exist, the third is new
            {"op": "paste", "text": text, "targets": [1, 2], "c": 1, "clip": "a\tb\nc\td\ne\tf"},
            # starts at the last column: the row grows two columns, the short row is padded with delimiters
            {"op": "paste", "text": text, "targets": [2], "c": 3, "clip": "x\ty"},
            {"op": "paste", "text": text + "\n", "targets": [1], "c": 0, "clip": "p\nq\nr"},
            {"op": "paste", "text": "", "targets": [], "c": 0, "clip": "a\tb\nc\td"},
            {"op": "paste", "text": "only", "targets": [0], "c": 0, "clip": "a\tb"},
            {"op": "paste", "text": "a\n", "targets": [0, 1], "c": 0, "clip": "x\ny"},
        ]
    )
    assert got[0] == [["a", "b"], ["c", "d"]]
    assert got[1] == [["x\ty", "l1\nl2"]]
    assert got[2] == "h1,h2,h3\n1,a,b\n4,c,d\n,e,f"
    assert got[3] == "h1,h2,h3\n1,2,3\n4,5,,x,y"
    assert got[4] == "h1,h2,h3\np,2,3\n4,5\nq\nr\n"
    assert got[5] == "a,b\nc,d\n"
    assert got[6] == "a,b"
    assert got[7] == "x\ny\n"


def test_the_grid_has_sort_filter_header_resize_and_paste_wired_in_the_recipes():
    """L-documents-39: the column menu is `kebabMenu`, the sort is a view until "Sort the file", every file write is one
    transaction with an Undo, widths are view state (never written), and a resize has a keyboard path."""
    assert "kebabMenu(" in JS and "ph-dots" not in JS
    #: Every change to the file goes through `structural` or `write`: one `dispatch`, so Ctrl+Z takes it back whole.
    assert JS.count("docCmView.dispatch(") == 1
    assert "structural(changes, null, `File sorted by" in JS and "structural(pasteBlock(" in JS
    assert 'toastAction(message, "Undo"' in JS
    #: The header choice is the only thing kept, per document; widths, sort and filters are not.
    assert JS.count("prefs.set(") == 1 and "HEADER_KEY" in JS
    #: A separator you can focus: Left, Right and Home, as well as the drag.
    assert 'setAttribute("role", "separator")' in JS and '"ArrowRight"' in JS and '"Home"' in JS
    css = (ROOT / "frontend" / "css" / "doc-csv-grid-lazy.css").read_text(encoding="utf-8")
    coarse = css.split("@media (pointer: coarse)", 1)[1]
    for selector in (".csv-grid-sort", ".csv-grid-filter", ".csv-grid-grip"):
        assert selector in coarse, selector
