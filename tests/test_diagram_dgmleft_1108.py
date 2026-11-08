"""dgmleft-1108: the diagram builder's open items, one test per commit (read for what each must hold)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _text(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_a_drop_over_a_dock_is_a_drop_on_the_picture():
    """Item 1: the zoom bar and the shelf sit on the picture, so a drop over them must still land (no dead spot)."""
    canvas = _text("diagram-canvas.js")
    over = canvas[canvas.index("function over(g, h)") : canvas.index("function wire(S, h)")]
    assert 'closest(".dock")' not in over and "stage?.contains(at)" in over
    seq = _text("diagram-seq-canvas.js")
    seq_over = seq[seq.index("function over(g)") : seq.index("const f = frameOf(S)")]
    assert ".dgm-zoom" not in seq_over and 'closest(".dock' not in seq_over


def test_menus_are_decorated_through_the_element_not_its_host():
    """Item 2: `openMenuAtPoint` returns the menu; the kind bar and the shelf decorate that, not a host lookup."""
    assert "return menu;" in _text("markdown.js").split("function openMenuAtPoint")[1].split("function linkMenuItems")[0]
    assert ".pointer-menu-host .action-menu" not in _text("diagram-kindbar.js")
    assert "const menu = openMenuAtPoint(" in _text("diagram-kindbar.js")
    assert "const menu = openMenuAtPoint(" in _text("diagram-library.js")


def test_coarse_handles_lean_fully_out_of_the_box():
    """Item 3: on `(pointer: coarse)` a handle's inner edge is on the box edge (measured 10 px of overlap at 390 before, 0 after)."""
    edges = _text("diagram-edges.js")
    assert "const out = coarse ? size / 2 : lean;" in edges and "ox * out" in edges
