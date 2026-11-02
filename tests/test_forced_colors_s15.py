"""Windows High Contrast has rules of its own (audit 1028 S15).

The CSS had one `forced-colors: active` rule (the sketch pad's) in 50,000
lines. In Chromium's forced-colors emulation the open top tab, the chosen
category and sub-tab, the pressed theme card and every filled button carried no
mark and the theme swatches were blank. `forced-colors-lazy.css` outlines what
is chosen, borders a filled button, and keeps swatch colour; `app.js` loads it
only while the media query matches, so no one else downloads it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEET = (ROOT / "frontend" / "css" / "forced-colors-lazy.css").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_sheet_is_only_a_forced_colors_block_in_system_colours():
    body = re.sub(r"/\*.*?\*/", "", SHEET, flags=re.S).strip()
    assert body.startswith("@media (forced-colors: active) {") and body.endswith("}")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|oklab|var\(--", body), "only system colours in forced-colours mode"
    for need in ("aria-selected", "aria-pressed", "aria-current", "forced-color-adjust: none", "Highlight", "ButtonText", "CanvasText"):
        assert need in body, need


def test_it_is_loaded_lazily_and_only_when_the_media_query_matches():
    assert 'matchMedia("(forced-colors: active)").matches) lazyScript("/css/forced-colors-lazy.css")' in APP
    assert "forced-colors-lazy" not in INDEX, "not a boot stylesheet: it would count against the boot CSS budget"
