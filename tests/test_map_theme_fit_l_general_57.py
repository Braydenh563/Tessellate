"""The map theme dialog fits a 900px window (L-general-57)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_groups_are_blocks_set_in_two_columns_when_wide():
    """Source text: L-general-57, maptheme.js: the dialog's one column was
    1002px tall in a 900px window and scrolled. Each group is now a block, and
    from 1100px the four blocks sit in two columns (669px measured)."""
    js = (ROOT / "frontend/js/whiteboard-map.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/css/library-lazy.css").read_text(encoding="utf-8")
    assert 'block.className = "wb-map-theme-group"' in js
    assert ".wb-map-theme-rows:has(> .wb-map-theme-group)" in css
    wide = css.split("@media (min-width: 1100px) {", 1)[1].split("\n}\n", 1)[0]
    assert "grid-template-columns: 1fr 1fr" in wide
