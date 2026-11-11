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

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(body: str) -> object:
    text = (JS / "documents-base.js").read_text(encoding="utf-8")
    region = text[text.index("// DOC-BASE-BEGIN") : text.index("// DOC-BASE-END")]
    script = "var window = {};\n(() => {\n" + region + "\nwindow.b = { parse, query };\n})();\nconst b = window.b;\n" + body
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
    docs = (JS / "documents.js").read_text(encoding="utf-8")
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
