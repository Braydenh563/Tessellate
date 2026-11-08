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
