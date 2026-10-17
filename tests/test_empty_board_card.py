"""INBOX 904 B24: the empty board's card is one tidy row of actions.

The owner: "awkward popup in board". Measured on a new board
(`scratchpad/ui-sweeps/emptyboard904.js`): the card was 173px tall with
"Keys and controls" on one row at the left and "Don't show this on new boards"
alone on a second row at the right (the foot's own flex row, plus the stray
`wb-empty-hint-close` margin on the button), the two buttons 46px apart in height
and 160px apart in width. Both now share the one actions row.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._css_paths import css_text

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _card() -> str:
    start = INDEX.index('class="wb-empty-hint-inner"')
    return INDEX[start : INDEX.index("<!-- **One top bar", start)]


def test_both_buttons_are_in_the_one_actions_row():
    card = _card()
    actions = card[card.index('id="wb-empty-hint-actions"') :]
    actions = actions[: actions.index("</div>")]
    assert 'id="wb-empty-hint-keys"' in actions and 'id="wb-empty-hint-dismiss"' in actions
    assert "wb-help-foot" not in card


def test_the_actions_row_spreads_its_two_buttons():
    css = css_text()
    rule = re.search(r"\.wb-empty-hint-actions\s*\{([^}]*)\}", css[css.rindex(".wb-empty-hint-actions") - 5 :])
    assert rule and "justify-content: space-between" in rule.group(1)
