"""INBOX 1620 f: the Dashboard constellation does not draw behind a modal.

At 4x CPU the 112 to 288 ms after a Dashboard or Settings press was the next
frame's render with the sketch drawing under the dialog. Measured with
`scratchpad` probe small3 (bgArt on, 4x CPU, Settings open): `draw` calls a
second behind the modal 30 before, 0 after. The check is one query per frame
in `p.draw`, which rests the loop; no new observer (wake-source ratchet).
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dash-art.js").read_text(encoding="utf-8")


def _draw() -> str:
    match = re.search(r"p\.draw = \(\) => \{.*?\n      \};", SRC, re.S)
    assert match, "p.draw is gone from dash-art.js"
    return match.group(0)


def test_the_loop_rests_while_a_modal_is_open():
    body = _draw()
    rest = body.index("rest();")
    assert '.modal-overlay:not(.hidden)' in body[:rest], "the modal check must come before the rest"
    assert body.index(".modal-overlay:not(.hidden)") < body.index("scene("), "nothing is drawn before the check"


def test_a_rest_is_ended_by_attention_not_by_a_new_observer():
    assert "new MutationObserver" not in SRC
