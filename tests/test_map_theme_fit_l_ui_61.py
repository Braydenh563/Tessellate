"""Source text: the map theme dialog fits a 900px window (L-ui-modernisation-61); its height is measured in the app
(scratchpad map sweeps), and this pins the CSS that keeps it there."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_groups_are_blocks_set_in_two_columns_when_wide():
    """Source text: L-ui-modernisation-61, maptheme.js: the dialog's one column was
    1002px tall in a 900px window and scrolled. Each group is now a block, and
    from 1100px the four blocks sit in two columns (669px measured)."""
    js = (ROOT / "frontend/js/whiteboard-map.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/css/library-lazy.css").read_text(encoding="utf-8")
    assert 'block.className = "wb-map-theme-group"' in js
    assert ".wb-map-theme-rows:has(> .wb-map-theme-group)" in css
    #: The block that holds the theme rows, not the first 1100px block: the
    #: Library CSS pass (L-ui-modernisation-51) moved another one above it.
    blocks = [b.split("\n}\n", 1)[0] for b in css.split("@media (min-width: 1100px) {")[1:]]
    wide = next((b for b in blocks if ".wb-map-theme-rows:has(> .wb-map-theme-group)" in b), "")
    assert "grid-template-columns: 1fr 1fr" in wide
