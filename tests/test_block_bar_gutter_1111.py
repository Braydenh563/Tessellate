"""The owner, 2026-11-11: the hover toolbar (edit, copy, delete) "covers the content in the top corner of that row".
The document block bar was centred on the block's top edge, over the last line above and the first words below. It now
stands in a column in the preview's right gutter. Measured in Chromium with a callout and three long paragraphs
(a throwaway sweep, see CHANGELOG): the bar's overlap with every text line and every block was 0 px² at 1440 and
390, and it stayed inside the preview (it was 611 to 833 px² over a block at 1440 before the gutter was reserved)."""

import re
from pathlib import Path

from tests._css_paths import FORMER_10, sheets

ROOT = Path(__file__).resolve().parents[1]
CSS = sheets(*FORMER_10)
BAR = (ROOT / "frontend" / "css" / "09-editor.css").read_text(encoding="utf-8") + (
    ROOT / "frontend" / "css" / "library-lazy.css"
).read_text(encoding="utf-8")  # L-ui-modernisation-31: Library-only rules live in the lazy sheet
JS = (ROOT / "frontend" / "js" / "documents-callouts.js").read_text(encoding="utf-8")


def test_the_bar_is_a_column() -> None:
    rule = BAR.split(".doc-block-bar {", 1)[1].split("}", 1)[0]
    assert "flex-direction: column" in rule


def test_the_preview_keeps_the_gutter_last_in_the_cascade_on_hover_devices() -> None:
    # Was the last hover block of 10-responsive.css; UI plan 13b moved it beside the editor (09), so it is
    # found by its declaration, and nothing loaded after it may set the preview's padding again.
    i = CSS.rindex("padding-right: calc(var(--target-min)")
    block = CSS[CSS.rindex("@media (hover: hover) {", 0, i) :]
    block = block[: block.index("\n}\n")]
    assert "#doc-panes.reading > #doc-preview" in block  # Read view's own padding must not take it back
    assert "--target-min" in block  # the room is the bar's width, whatever the target size
    later = re.sub(r"/\*.*?\*/", "", CSS[i:].split("\n}\n", 1)[1], flags=re.S)
    assert not re.search(r"#doc-preview[^{]*\{[^}]*padding", later)


def test_the_bar_is_placed_right_of_the_block_and_inside_the_preview() -> None:
    body = JS.split("const rect = block.getBoundingClientRect();", 1)[1].split("docPlaceFixed", 1)[0]
    assert "rect.right" in body and "host.right - width" in body
    assert "offsetHeight / 2" not in body  # no longer straddles the block's top edge
