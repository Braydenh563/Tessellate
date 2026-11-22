"""The board gallery sits inside `#library-view-whiteboard`, which clips (`overflow: clip`, INBOX 421 a: a canvas
never scrolls). Without a scroller of its own a gallery taller than the window was unreachable: at 390x844 with
about forty boards, `#library-view-whiteboard` was 712px tall over 6809px of cards, and a board past the fold could
not be scrolled to or opened (deepflows mindmap and whiteboard @390, 2026-11-22). After: the landing scrolls,
705px over 6821px, and both flows pass."""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css" / "06-timeline-dialogs.css"


def _block(css: str, selector: str) -> str:
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def test_the_gallery_scrolls_and_the_canvas_still_clips() -> None:
    css = CSS.read_text(encoding="utf-8")
    landing = _block(css, "#wb-boards-landing")
    assert "overflow-y: auto" in landing and "height: 100%" in landing
    view = _block(css, "#library-view-whiteboard")
    assert "overflow: clip" in view and "touch-action: none" in view
