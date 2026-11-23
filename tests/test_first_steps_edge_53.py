"""Source text: L-ui-modernisation-53, the density census's alignment column
(scratchpad/ui-sweeps/density.js, near misses). On Home the first-steps card
sat its heading at 27px while every widget card below it starts its text at
30px: the card's sides were `--space-4` (9.6px) where a Home widget's are
`--panel-pad` (12.8px), a 3px ragged edge down the first column. The card
takes the widgets' side padding, so the column shares one edge."""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def _rule(text: str, selector: str) -> str:
    match = re.search(rf"(?m)^{re.escape(selector)} \{{([^}}]*)\}}", text)
    assert match, selector
    return match.group(1)


def test_first_steps_sides_match_the_home_widgets():
    first = _rule((CSS / "first-run-lazy.css").read_text(), ".first-steps")
    widget = _rule((CSS / "00-tokens-shell.css").read_text(), ".dash-widget")
    assert "--card-pad-x: var(--panel-pad);" in widget
    assert re.search(r"padding: var\(--space-3\) var\(--panel-pad\);", first), first
