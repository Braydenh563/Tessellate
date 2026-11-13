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
