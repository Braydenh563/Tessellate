"""A board's resting cards carry no grips, so a pan does not layerize them.

**Why this exists (INBOX 424 (a), the board pan's `Layerize`).** Every card and
text box on a board draws eight resize handles and a rotate grip as children,
and until 2026-09-26 they were `opacity: 0` at rest rather than absent. Each
one carries `transform: scale(var(--wb-inv-zoom))` so it stays one size to the
hand, and a scale is a transform the compositor cannot fold into the layer
around it, so every grip was a paint chunk of its own that broke the cards
into separate layers. Measured on a 250-object board at 4x CPU
(`scratchpad/ui-sweeps/gwperf.js`, `scratchpad/ui-sweeps/wbpanlayers.js`):
256 composited layers at rest, 245 of them "Overlap", and a 40-move pan spent
1,680ms in `Layerize` (a full pass per frame, because the pan's own transform
change is not a direct update). With the grips out of the tree at rest, 138
layers and 388ms. The grips are still drawn, at full size and with the fade,
on the card that is hovered or selected in the Select tool, which is the only
place they were ever visible.

The suite cannot composite a page, so this holds the two halves of the rule as
text: the grips are `display: none` until the reveal, and the reveal puts them
back.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: The whiteboard blocks moved from 07-whiteboard-misc.css to library-lazy.css (L-world-class-350).
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _rule(selector_start: str) -> str:
    """The body of the first rule whose prelude starts with `selector_start`."""
    text = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    idx = text.index("\n" + selector_start) + 1
    return text[text.index("{", idx) + 1 : text.index("}", idx)]


def test_a_resting_grip_is_not_in_the_tree():
    for grip in (".wb-resize-handle {", ".wb-rotate-handle {"):
        body = _rule(grip)
        assert "display: none" in body, (
            f"{grip.rstrip(' {')} must be `display: none` at rest: an invisible "
            "grip is still a scaled paint chunk, and 1,620 of them on a "
            "250-object board cost a pan 1.3s of Layerize at 4x (INBOX 424 (a))"
        )


def test_the_reveal_puts_the_grips_back():
    body = _rule('#whiteboard-container[data-current-tool="select"] .wb-object:hover:not(.wb-in-group) .wb-resize-handle')
    assert "display: block" in body
    assert "opacity: 1" in body
    #: The fade in has to start from somewhere once the grip was absent: a
    #: `display` change skips the transition unless the start is declared.
    assert "@starting-style" in CSS
