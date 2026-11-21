"""Source text: a right-click menu opens at the pointer, not 14px from it (L-ui-modernisation-60); placement is
measured by the anchorsmotion sweep, and this pins the 1x0 pointer anchor that gives it."""

from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend/css/02-chat-graph.css").read_text(encoding="utf-8")


def test_the_pointer_pixel_is_a_block_with_no_height():
    """Source text: L-ui-modernisation-60, anchorsmotion.js rowmenu at 1440x600: the
    menu opened 14px from the pointer. The inline-block wrap set the pixel on
    its line's baseline (9px down) and a stronger button rule kept 4px padding
    each side. The wrap and the pixel are now blocks, the pixel 1px by 0."""
    wrap = CSS.split(".pointer-menu-host > .menu-wrap {", 1)[1].split("}", 1)[0]
    pixel = CSS.split(".pointer-menu-host > .menu-wrap > .pointer-menu-anchor.pointer-menu-anchor {", 1)[1].split("}", 1)[0]
    assert "display: block" in wrap and "line-height: 0" in wrap
    assert "display: block" in pixel and "height: 0;" in pixel and "padding: 0;" in pixel
