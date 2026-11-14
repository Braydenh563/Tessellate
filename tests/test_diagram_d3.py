"""The kinds the blocks do not draw (1546 D3) and a diagram over 120 blocks: each opens in Source with its picture and
one line saying why. Read here for the names and the wording; the numbers (each kind's note, a picture drawn, the
document on Split and the dialog on Source, 130 blocks) were taken by scratchpad/ui-sweeps/diagram-d3.js, retired under the scratchpad cap
(`git show cbb5ecf:scratchpad/ui-sweeps/diagram-d3.js`).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "frontend" / "js" / "diagram-builder.js").read_text(encoding="utf-8")
#: The names and the limit live with the pure ops (the lazy diagram-ops.js, 1594), the sentence in the builder.
OPS = (ROOT / "frontend" / "js" / "diagram-ops.js").read_text(encoding="utf-8")


def test_a_kind_the_blocks_do_not_draw_and_a_diagram_over_120_blocks_open_in_source_with_one_line_why():
    # State, class, pie, Gantt and ER became block kinds (L-documents-57), so only these two still open in Source.
    for kind in ("user journeys", "C4 diagrams"):
        assert f'"{kind}"' in OPS, kind
    assert "so it opens in Source with its picture." in BUILDER and "has more than ${diagramOps.MAX} blocks" in BUILDER
    assert "const DGB_MAX = 120;" in OPS



def test_on_a_phone_the_preview_that_holds_such_a_diagram_has_a_width_and_shows_its_picture_before_the_line():
    """Measured at 390 on a state diagram in Split: the preview was 32 px wide (the pane is a size container, so
    its content asks for no width, and the stacked preview did not stretch), so the picture was not there."""
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    assert "#doc-preview:has(> .dgm) {\n  width: 100%;" in css
    assert ".dgm-plain .dgm-hint {\n    order: 1;" in css
    assert "@media (max-width: 599.98px) {\n  .dgm-plain {\n    height: auto;" in css
