"""dog1-1025 leftovers (fixa2). Browser checks: scratchpad/ui-sweeps/capturesave.js."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_capture_box_scrolls_inside_so_save_stays_in_view():
    # The stretch rule frees a scroller from its max-height; the capture box is
    # a stretched item too, and 30 lines pushed Save to y=981 at 800 high.
    assert "#capture .note-surface-stretch .cm-editor .cm-scroller" in LAZY_CSS
    assert "#capture .capture-commit-row {\n  position: sticky;" in LAZY_CSS
