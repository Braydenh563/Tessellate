"""The ```base block (DOCUMENTS_PLAN gap row 6): a read-only table of notes by property.

The fence's reader runs in node; the wiring that needs a browser is checked as
text: Read swaps the fence, Live draws it through the same state field the graph
uses, the "/" menu offers it, and the module is lazy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(body: str) -> object:
    text = (JS / "documents-base.js").read_text(encoding="utf-8")
    region = text[text.index("// DOC-BASE-BEGIN") : text.index("// DOC-BASE-END")]
    script = "var window = {};\n(() => {\n" + region + "\nwindow.b = { parse, query, setLine, groupRows, moveValue, monthGrid, dateOf, queryParse, queryAddress };\n})();\nconst b = window.b;\n" + body
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@node
def test_a_fence_reads_as_a_query_and_names_the_lines_it_cannot() -> None:
    got = _run(
        "const m = b.parse('type: Book\\nwhere: status = read\\nwhere: tags=x\\ncolumns: author, rating\\nsort: rating desc\\nlimit: 5\\nbogus line\\nwhere: nothing\\nlimit: lots');"
        "console.log(JSON.stringify({ m, url: b.query(m) }));"
    )
    m = got["m"]
    assert m["type"] == "Book" and m["where"] == [["status", "read"], ["tags", "x"]]
    assert m["columns"] == ["author", "rating"] and m["sort"] == "rating" and m["desc"] is True and m["limit"] == 5
    assert len(m["errors"]) == 3
    assert got["url"] == "/property-table?type=Book&where=status%3Dread&where=tags%3Dx&columns=author%2Crating&sort=rating&desc=true&limit=5"


@node
def test_sort_without_a_direction_is_ascending_and_the_limit_is_capped() -> None:
    got = _run("const m = b.parse('type: Movie\\nsort: release date\\nlimit: 99999'); console.log(JSON.stringify(m));")
    assert got["sort"] == "release date" and got["desc"] is False and got["limit"] == 300 and got["errors"] == []


def test_read_and_live_draw_the_fence_and_the_module_is_lazy() -> None:
    math = (JS / "documents-math.js").read_text(encoding="utf-8")
    docs = documents_text()
    editor = (JS / "editor.js").read_text(encoding="utf-8")
    assert "docMathRender.graphIn(preview);\n  docMathRender.baseIn(preview);" in docs
    assert "docMathRender.baseField(CM)" in docs
    assert 'module: "docBase"' in math
    assert 'docBase: ["/css/doc-base-lazy.css", "/js/documents-base.js"]' in (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert '{ id: "base"' in editor and "```base" in editor
    source = (JS / "documents-base.js").read_text(encoding="utf-8")
    for banned in ("eval(", "new Function", "innerHTML", "insertAdjacentHTML"):
        assert banned not in source, banned
    css = (ROOT / "frontend" / "css" / "doc-base-lazy.css").read_text(encoding="utf-8")
    assert css.count("{") == css.count("}") and "!important" not in css and "style=" not in css


@node
def test_the_view_lines_are_read_and_written_back_into_the_fence() -> None:
    got = _run(
        "const m = b.parse('type: Task\\ncolumns: status\\nview: Board\\ngroup: status\\ndate: due\\nview: wall');"
        "const s = 'type: Task\\nview: board\\ncolumns: status';"
        "console.log(JSON.stringify({ m, url: b.query(m),"
        " a: b.setLine(s, 'view', 'calendar'), c: b.setLine(s, 'view', ''), d: b.setLine(s, 'group', 'status') }));"
    )
    m = got["m"]
    assert m["view"] == "board" and m["group"] == "status" and m["date"] == "due" and len(m["errors"]) == 1
    assert "columns=status%2Cdue" in got["url"]
    assert got["a"] == "type: Task\nview: calendar\ncolumns: status"
    assert got["c"] == "type: Task\ncolumns: status"
    assert got["d"].endswith("\ngroup: status")


@node
def test_a_board_groups_by_each_value_and_a_move_swaps_one_entry() -> None:
    got = _run(
        "const rows = [{ id: 1, title: 'A', values: { s: ['todo'] } }, { id: 2, title: 'B', values: { s: ['done', 'todo'] } },"
        " { id: 3, title: 'C', values: {} }];"
        "console.log(JSON.stringify({ g: b.groupRows(rows, 's').map((x) => [x.name, x.rows.map((r) => r.id)]),"
        " m1: b.moveValue(['a', 'b'], 'a', 'c'), m2: b.moveValue(['a'], 'a', ''), m3: b.moveValue('todo', 'todo', 'done'),"
        " m4: b.moveValue(undefined, '', 'done'), m5: b.moveValue(['a', 'b'], 'a', 'b') }));"
    )
    assert got["g"] == [["done", [2]], ["todo", [1, 2]], ["", [3]]]
    assert got["m1"] == ["b", "c"] and got["m2"] is None and got["m3"] == "done" and got["m4"] == "done"
    assert got["m5"] == ["b"]


@node
def test_the_calendar_is_six_monday_first_weeks_and_rows_land_by_their_date() -> None:
    got = _run(
        "const g = b.monthGrid(2026, 10);"
        "console.log(JSON.stringify({ n: g.length, first: g[0], last: g[41], inMonth: g.filter((c) => c.inMonth).length,"
        " d: b.dateOf({ values: { due: ['2026-11-14T09:00'] } }, 'due'), none: b.dateOf({ values: { due: ['soon'] } }, 'due') }));"
    )
    assert got["n"] == 42 and got["inMonth"] == 30
    assert got["first"]["iso"] == "2026-10-26" and got["last"]["iso"] == "2026-12-06"
    assert got["d"] == "2026-11-14" and got["none"] == ""


def test_the_views_are_wired_to_the_recipes() -> None:
    source = (JS / "documents-base.js").read_text(encoding="utf-8")
    math = (JS / "documents-math.js").read_text(encoding="utf-8")
    assert 'el("div", "seg seg-compact db-views")' in source and "kebabMenu(items" in source
    assert 'method: "PUT"' in source and "/properties" in source
    assert 'draggable = true' in source and "Move to " in source
    assert "fenceWrite(lang" in math and "fill: (figure, source, write)" in math


@node
def test_a_query_block_names_a_saved_search_or_holds_the_words() -> None:
    got = _run(
        "const saved = [{ name: 'Reading list', query: 'tag:book is:unread' }];"
        "const a = b.queryParse('Reading list\\nlimit: 500'); const c = b.queryParse('search: tag:work\\nlimit: x');"
        "const d = b.queryParse('saved: reading LIST'); const e = b.queryParse('plain words');"
        "console.log(JSON.stringify({ a, c, ra: b.queryAddress(a, saved), rc: b.queryAddress(c, saved),"
        " rd: b.queryAddress(d, saved).q, re: b.queryAddress(e, saved).q, none: b.queryAddress(b.queryParse(''), saved).q }));"
    )
    assert got["a"]["name"] == "Reading list" and got["a"]["limit"] == 50
    assert got["ra"]["q"] == "tag:book is:unread" and "kind=note%2Cdocument" in got["ra"]["path"] and got["ra"]["label"] == "Reading list"
    assert got["c"]["text"] == "tag:work" and len(got["c"]["errors"]) == 1 and got["rc"]["q"] == "tag:work"
    assert got["rd"] == "tag:book is:unread" and got["re"] == "plain words" and got["none"] == ""


def test_the_query_block_is_wired_in_read_live_the_menu_and_the_save() -> None:
    docs = documents_text()
    assert "docMathRender.queryIn(preview)" in docs and "docMathRender.queryField(CM)" in docs
    assert 'new CustomEvent("doc-saved")' in docs
    assert '"doc-saved"' in (JS / "documents-base.js").read_text(encoding="utf-8")
    assert '{ id: "query"' in (JS / "editor.js").read_text(encoding="utf-8")


def test_a_calendar_day_prints_its_whole_title_and_no_card_splits_across_sheets() -> None:
    """L-documents-84: on paper a day's note name was cut by the screen's ellipsis (measured at 520px: 90px of a name clipped)."""
    css = (ROOT / "frontend" / "css" / "doc-base-lazy.css").read_text(encoding="utf-8")
    printed = css[css.rindex("@media print") :]
    assert ".db-day .db-open" in printed and "white-space: normal" in printed
    assert "break-inside: avoid" in printed and ".db-card" in printed


def test_the_table_is_read_again_after_each_save_and_keeps_its_rows_on_screen_meanwhile() -> None:
    """L-documents-85: only the query block listened for `doc-saved`; a table, board or calendar showed the rows as they were."""
    source = (JS / "documents-base.js").read_text(encoding="utf-8")
    fill = source[source.index("function fill(figure, source, write)") : source.index("function queryFill")]
    assert 'document.addEventListener("doc-saved", again)' in fill and 'removeEventListener("doc-saved", again)' in fill
    assert "if (!current) body.replaceChildren" in fill, "a refresh must not blank the rows it is about to redraw"
