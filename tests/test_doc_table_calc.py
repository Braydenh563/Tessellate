"""Table formulas and the filter row (DOCUMENTS_PLAN gap row 12).

A cell that is `=SUM(B)`, `=AVG(B2:B4)` or `=COUNT(C)` shows its result in Live
and Read; the markdown keeps the formula. The filter hides body rows whose
column does not contain the text, and edits nothing. Pure string work, run in
node like `test_doc_table_manage.py`; the drawn half is
`scratchpad/ui-sweeps/` (driven in Chromium, numbers in s9c-1110.md).
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
const grid = [["Item", "Qty", "Price"], ["pear", "10", "$1.50"], ["apple", "2", "3"], ["fig", "", "1,000"], ["Total", "=SUM(B)", "=SUM(C2:C4)"]];
const f = (t) => docTableFormula(t, grid);
eq("sum a column skips header, blanks and the formula itself", f("=SUM(B)"), "12");
eq("sum a range takes money and thousands", f("=sum(C2:C4)"), "1004.5");
eq("avg of numbers present", f("=AVG(B2:B4)"), "6");
eq("average is a spelling of avg", f("=AVERAGE(B)"), "6");
eq("count counts numbers only", f("=COUNT(B2:B4)"), "2");
eq("min and max", [f("=MIN(C)"), f("=MAX(C)")], ["1.5", "1000"]);
eq("two column range", f("=SUM(B2:C3)"), "16.5");
eq("a plain cell is not a formula", f("12"), null);
eq("an unknown function is not a formula", f("=FOO(B)"), null);
eq("a column past the table is #REF", f("=SUM(Z)"), "#REF");
eq("avg of nothing is #N/A", docTableFormula("=AVG(A)", grid), "#N/A");
eq("spaces are allowed", f(" = SUM( B2 : B3 ) "), "12");
eq("float noise is trimmed", docTableFormula("=SUM(A)", [["x"], ["0.1"], ["0.2"]]), "0.3");
const t = docTableParse("| a | b |\n| --- | --- |\n| 1 | x |\n| 22 | y |\n| 3 | xx |", 0);
eq("filter hides rows without the text", docTableFilterHidden(t, 1, "x"), [3]);
eq("filter is case blind and any-column with -1", docTableFilterHidden(t, -1, "XX"), [2, 3]);
eq("empty needle hides nothing", docTableFilterHidden(t, 0, ""), []);
eq("filter never hides the header or the delimiter", docTableFilterHidden(t, 0, "zzz"), [2, 3, 4]);
eq("the grid of a table is its text cells", docTableValues(t), [["a", "b"], ["1", "x"], ["22", "y"], ["3", "xx"]]);
process.stdout.write(JSON.stringify(out));
"""


def test_formulas_and_the_filter_are_exact(tmp_path) -> None:
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = tmp_path / "calc.js"
    script.write_text(table_model_source() + DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    results = json.loads(out.stdout)
    failed = [r for r in results if not r["ok"]]
    assert not failed, failed
    assert len(results) >= 18
