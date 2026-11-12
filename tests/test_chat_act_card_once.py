"""A reminder said once (the chat88 hand-back: "the remind me answer's text
appears twice in the bubble's innerText").

Drawn twice, not a text-extraction quirk: the server streams the sentence as
the answer *and* as the act card's summary, and the card drew its own copy
(measured at 1440 and 390: the sentence was in a `p` of the bubble and in a
`p > span.ph-text` of `.tool-confirm`). A run that already ran now draws only
Undo on the card; the sentence stays its accessible name.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "frontend" / "js" / "ask-compose.js").read_text(encoding="utf-8")


def test_a_done_acts_card_does_not_repeat_the_answer():
    body = SRC[SRC.index("function renderActCard(") :]
    body = body[: body.index("\n}\n")]
    assert re.search(r"const done = \(summary, undo, steps, said = false, again = false\)", body)
    assert 'card.setAttribute("aria-label", summary)' in body
    assert 'if (event.done || event.state === "done") done(event.summary || event.label, event.undo, event.steps, Boolean(event.done), restored);' in body
    # The Confirm path is the only place its sentence is drawn, so it still is.
    assert "done(result.summary, result.undo, event.steps)" in body
    assert "if (card.childElementCount) holder.appendChild(card);" in body
