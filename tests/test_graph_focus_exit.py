"""L-graph-17: leaving focus puts the whole map back where it was.

Measured with a 2,000-note map (focus on one note, then back to every note,
Playwright, 9 s settles): before, notes moved up to 755 px (mean 215); after,
0 and 0. The focus view's few notes were the only prior, so the whole map
re-simulated; now its spots are kept on the way in and held like a saved
view's on the way out (alpha 0 when every note is placed)."""

from __future__ import annotations

from pathlib import Path

from tests._js_scope import unwrapped

CANVAS = unwrapped((Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def test_the_whole_maps_spots_are_kept_on_the_way_into_focus() -> None:
    assert "if (focusing && !s.focusAt && prior.size) {" in CANVAS
    assert "Number.isFinite(at.x) && Number.isFinite(at.y)" in CANVAS
    # Moving focus from one note to another keeps the first stash; only the
    # whole map clears it.
    assert "if (!focusing) s.focusAt = null;" in CANVAS


def test_the_way_out_holds_them_like_a_saved_view() -> None:
    assert "const back = !focusing && s.focusAt && prior.size ? s.focusAt : null;" in CANVAS
    assert "graphPendingViewPositions || back ||" in CANVAS
    assert "alpha: heldForAdd ? GC_ADD_ALPHA : viewPositions && !unplacedByView ? 0 : 1," in CANVAS
