"""A Size or Colour change redraws; it does not lay the map out again (audit G4).

The layout signature (`gcStartWorker`) decides whether a settled map is held.
It listed each dot's radius, so the Size rule changed the signature and every
change re-ran the settle (about 12 s of work at 2,000 notes). Measured in the
app at 2,000 notes: a Size and a Colour change post `init` with alpha 0, the
signature is unchanged and the map stays settled.
"""

from pathlib import Path

CANVAS = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _signature() -> str:
    start = CANVAS.index("const sig = JSON.stringify([")
    return CANVAS[start : CANVAS.index("]);", start)]


def test_the_layout_signature_leaves_out_the_radius():
    sig = _signature()
    assert "n.fx, n.fy]" in sig
    assert "n.r" not in sig


def test_the_signature_still_covers_what_changes_the_layout():
    sig = _signature()
    for part in ("init.edges", "init.params", "world", "init.perf"):
        assert part in sig
