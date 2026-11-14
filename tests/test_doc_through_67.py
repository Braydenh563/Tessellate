"""L-documents-67: the caret readout says how far through a long document it is (DOCUMENTS_PLAN 17d).

Measured 2026-11-14 (scratchpad t646-through.js, 1440x900): a 50-line document reads `Ln 25, Col 1` (69 px wide);
a 400-line one at line 200 reads `Ln 200, Col 1 · 50%` (114 px wide, 12 px, the readout's own muted colour, no new
element). At 390 px the readout is display none for both, as before (the bar folds it), so the figure is a wide-window one.
"""

from __future__ import annotations

from pathlib import Path

DOCS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def _stats() -> str:
    start = DOCS.index("function docCaretStats(box)")
    return DOCS[start : DOCS.index("function docSetStatusText", start)]


def test_the_figure_is_the_caret_line_of_the_last_line_and_only_from_200_lines():
    body = _stats()
    assert "const last = box.lineAt(Infinity).number;" in body
    assert "through: last >= 200 ? Math.round((line.number / last) * 100) : -1," in body
    # No pass over the text: the line index answers, so a keystroke in a long document stays O(log n).
    assert "split(" not in body.split("const last")[1]


def test_the_readout_appends_it_after_the_column_and_before_the_selection():
    assert 'const through = stats.through >= 0 ? ` · ${stats.through}%` : "";' in DOCS
    assert "`Ln ${stats.line}, Col ${stats.column}${through}${selection}`" in DOCS
