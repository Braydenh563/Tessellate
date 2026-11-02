"""Documents audit 1102, the quick wins (DX2, DX8, DX17, DX18, DX20, DX21, DX22).

Each test pins the cause the audit measured in a browser, so the fix cannot
quietly go back. The numbers are in CHANGELOG.md and the agent's remaining list.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import documents_text

CSS = "".join(p.read_text(encoding="utf-8") for p in sorted(Path("frontend/css").glob("*.css")))


def _fn_body(js: str, name: str) -> str:
    return js.split(f"function {name}(")[1].split("\n}\n")[0]


def test_dx2_live_table_columns_have_a_floor():
    """`minmax(0, 1fr)` shared 14 columns 594px (42px each) and wrapped a word
    one letter per line. A column has a floor and the line is as wide as its
    columns, so the editor scrolls sideways as the Read view does."""
    js = documents_text()
    body = _fn_body(js, "docTableGridRules")
    assert "minmax(0, 1fr)" not in body
    assert "minmax(var(--doc-table-col-min), 1fr)" in body
    assert "minWidth" in body and "--doc-table-col-min" in body.split("minWidth")[1]
    assert re.search(r'"--doc-table-col-min":\s*"6em"', js)
    assert '"minmax(0, 1fr)"' not in js.split('".cm-md-table-wide"')[1].split("}")[0]
