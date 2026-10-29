"""Audit 1029 H1: a card that waits on the person is output, never a step.

A step group folds shut ("Finished 1 step") when the model's prose follows,
so a Confirm filed inside it was invisible and the delete silently never ran.
`showWaiting` is the one way a waiting card reaches the page; the browser
half was measured with the fake model (parked `delete_note`, then prose).
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
AGENT = (JS / "chat-agent.js").read_text("utf-8")
ATTACH = (JS / "chat-attach.js").read_text("utf-8")


def _listed() -> list[str]:
    """Every function in chat-agent.js that draws a card with a button."""
    names = []
    for match in re.finditer(r"\nfunction ((?:render|plan)\w+)\(", AGENT):
        body = AGENT[match.end() : AGENT.index("\n}\n", match.end())]
        if 'className = "tool-confirm' in body or "agent-question" in body:
            names.append(match.group(1))
    assert names, "the scan found no waiting card at all"
    return names


def test_each_listed_card_is_drawn_by_the_helper_in_chat():
    for name in _listed():
        sites = [m.start() for m in re.finditer(rf"\b{name}\b", ATTACH)]
        assert sites, f"{name} is never drawn in chat-attach.js"
        for at in sites:
            assert ATTACH[max(0, at - 80) : at].rstrip().endswith("showWaiting(recordsHolder,") or "showWaiting(event.type" in ATTACH[max(0, at - 80) : at], name


def test_no_card_is_filed_into_the_step_group():
    assert not re.search(r"timeline\.tool\(\s*card", ATTACH)
    assert "timeline.tool(card" not in AGENT


def test_regenerate_keeps_the_old_answer_to_put_back():
    """Audit 1029 H7: Stop on a regenerate used to leave a blank."""
    edit = (JS / "chat-edit.js").read_text("utf-8")
    assert "restore: lastAssistant" in edit
    assert "opts.restore" in ATTACH and "appendChild(opts.restore)" in ATTACH


def test_a_silent_model_gets_a_waiting_line():
    """Audit 1029 H8: no word from the model for 8 s says so, once."""
    assert "heard" in ATTACH and "Waiting for the model…" in ATTACH
    
