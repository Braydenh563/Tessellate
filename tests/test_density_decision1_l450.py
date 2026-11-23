"""Source text: UI plan Phase 12 decision 1 (2026-10-10): "panel padding 12px;
the sidebar gutter 8px" (L450).

The card pair is one token set, so a panel and a compact widget both take
the 12px inset, and the sidebar's column gap is the 8px step, not the page's
edge gutter.
"""

from __future__ import annotations

import re

from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css" / "00-tokens-shell.css"


def _rule(css: str, selector: str) -> str:
    return css.split(selector + " {", 1)[1].split("\n}", 1)[0]


def test_panels_pad_twelve():
    css = CSS.read_text(encoding="utf-8")
    assert "--panel-pad: calc(0.75rem * var(--density));" in css
    assert css.count("--card-pad-y: var(--panel-pad);") >= 2
    assert css.count("--card-pad-x: var(--panel-pad);") >= 2


def test_the_sidebar_gutter_is_eight():
    css = CSS.read_text(encoding="utf-8")
    block = _rule(css, ".layout")
    assert re.search(r"(?<![-\w])gap: var\(--space-3\);", block)
