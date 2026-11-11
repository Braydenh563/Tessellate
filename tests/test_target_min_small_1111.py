"""OPEN #347: Text size "Small" (root 14.5px) put the phone tap targets under 44 px.

`--target-min` was 2.75rem, which is 44px only at the default 16px root; at Small it
measured 39.9px (Chromium, 390 wide, `data-fontsize="small"`). A finger does not
shrink with the caption size, so the floor is in CSS pixels as well as rem: Large still
steps up with its root, Small and Normal stop at 44.
"""

import re

from tests._css_paths import CSS_DIR, css_text


def _css() -> str:
    return css_text()


def test_the_touch_floor_is_never_under_44_css_pixels() -> None:
    css = _css()
    block = css[css.index("/* --- 1. touch targets, one step, one block"):]
    root = re.search(r":root \{\s*--target-min: ([^;]+);", block)
    assert root, "the touch block no longer sets --target-min on :root"
    assert root.group(1) == "max(2.75rem, 44px)", root.group(1)


def test_the_tab_bar_and_header_floors_are_44_pixels_at_small_text() -> None:
    css = _css()
    assert re.search(r"#tab-bar \{\s*--target-min: max\(2\.75rem, 44px\);", css)
    # The header is capped at 44 so Large cannot widen it; the cap is now also its floor.
    assert re.search(r"header#top-bar \{\s*--target-min: 44px;", css)
    assert "--target-min: min(2.75rem, 44px)" not in css
    assert not re.search(r"--target-min: 2\.75rem;", css)
    pad = (CSS_DIR / "sketch-pad.css").read_text(encoding="utf-8")
    assert "--target-min: max(2.75rem, 44px);" in pad and "--target-min: 2.75rem;" not in pad
