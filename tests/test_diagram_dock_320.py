"""The diagram builder's dock is one row at 320 px too, with 44 px targets.

At 390 the kind button (sample and caret), Add, the blocks list, Undo and the menu fit one row;
at 320 they need 280 px against 270, so the dock took a second row (110 px tall, measured with
the sweep named in CHANGELOG). `dgm-tight` (360 px or less, set in `more()`: a script's
matchMedia, not a new width in the stylesheets) drops the kind button's caret and the dock's
side padding and gaps, and keeps the dock from wrapping. Measured by driving the app at 320 and
390 in a phone emulation; this holds the wiring.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
BUILDER = (ROOT / "frontend" / "js" / "diagram-kindbar.js").read_text(encoding="utf-8")


def test_the_builder_marks_a_tight_phone() -> None:
    assert 'S.root.classList.toggle("dgm-tight", matchMedia("(max-width: 360px)").matches)' in BUILDER


def test_a_tight_dock_does_not_wrap_and_drops_the_caret() -> None:
    rule = re.search(
        r"\.dgm-dialog \.dgm-tight \.dgm-dock,\n\.dgm-dialog \.dgm-tight \.dgm-dock:has\(> \.dgm-addsplit\) \{([^}]*)\}",
        CSS,
    )
    assert rule and "flex-wrap: nowrap" in rule.group(1)
    caret = re.search(r"\.dgm-tight \.dgm-kindbtn \.ph-caret-down \{([^}]*)\}", CSS)
    assert caret and "display: none" in caret.group(1)
    assert re.search(r"\.dgm-narrow \.dock-group:has\(> \.dgm-dirs\) \{[^}]*display: none", CSS), "the empty direction group made a gap"


def test_no_new_width_query() -> None:
    assert "360px" not in CSS and "359" not in CSS
