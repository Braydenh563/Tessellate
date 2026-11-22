"""The Capture card's "Add to this note" row stays one line at 1024px (L-world-class-82).

Measured 2026-11-14 with Playwright at 768, 900, 1024, 1100 and 1200: the row is
36px tall (one line) at each, the five tools icon-only below 72rem. The rule
that does it is named buttons at `max-width: 72rem`; this holds its shape.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
TOOLS = ("entry-attach-file", "entry-attach-existing", "sketch-btn", "mic-note", "improve-btn")


def test_the_five_capture_tools_lose_their_words_at_or_above_1024():
    block = re.search(r"@media \(max-width: 72rem\) \{(.*?)\n\}\n", CSS, re.S)
    assert block, "the 72rem collapse is gone"
    head = block.group(1).split("font-size: 0;", 1)[0].rsplit("}", 1)[-1]
    for ident in TOOLS:
        assert f"#{ident}" in head, ident
    assert 72 * 16 > 1024
