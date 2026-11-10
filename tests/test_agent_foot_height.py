"""The popup agent's foot is its content's height in every mode (CHAT_PLAN B4).

The owner, 2026-11-05: "when fullscreen or docked to the main window, the
bottom footer of te popup agent is really really tall which it shouldnt be".
Docked or maximised, panelMovable gives the card the zone's height (803px at
1440 by 900) while its rows kept their floating 453px, the conversation capped
at 25rem, so 378px sat under the status row. A sized card gives that height to
the conversation (or the starters before there is one), and the foot stays
one control high: measured 45px with 29px under it (the grip row) floating,
docked left, docked right and maximised.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAZY = ROOT / "frontend" / "css" / "panel-movable-lazy.css"
BOOT = ROOT / "frontend" / "css" / "07-whiteboard-misc.css"


def _rule(css: str, selector: str) -> str:
    start = css.index(selector)
    return css[start : css.index("}", start)]


def test_a_sized_agent_gives_its_height_to_the_conversation() -> None:
    css = LAZY.read_text(encoding="utf-8")
    rule = _rule(css, '.command-palette-card.panel-movable-on[style*="height"] > :is(.command-palette-results, .command-palette-intro)')
    assert "flex: 1 1 auto;" in rule and "max-height: none;" in rule


def test_the_foot_never_grows() -> None:
    css = BOOT.read_text(encoding="utf-8")
    rule = _rule(css, ".command-palette-foot {")
    # a row of content height: no grow, no fixed or minimum height
    assert not re.search(r"\b(flex(-grow)?:\s*1|min-height|height):", rule)
