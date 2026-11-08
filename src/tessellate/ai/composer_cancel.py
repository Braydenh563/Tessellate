"""Dropping the act that waits for Confirm (CHAT_PLAN X17): "cancel", "never
mind", "forget it" after a card the page still shows open.

The server keeps no conversation, so the page says which card is open: the
turn before carries `pending_act`, the card's label, only while it waits
(`Dialogue.pending_act`). With nothing waiting these words are not read here
and fall through as they always did ("cancel the dentist task" is the task act,
`task_acts`). The reply is one line and an `act` event with `cancel` set,
which the page answers by closing the open card (`renderActCard`). Nothing is
written. Questions are read lower case with blanks collapsed.
"""

from __future__ import annotations

import re

from tessellate.ai.composer_dialogue import Dialogue

#: The whole message, so "cancel my gym membership note" is never taken for it.
_CANCEL = re.compile(
    r"^(?:(?:ok|okay|actually|no|nah|oh|hmm|um|please|just) )*"
    r"(?:cancel(?: (?:that|it|this|the (?:change|card|act)))?|never ?mind(?: (?:that|it))?|forget (?:it|that|about it)|scrap (?:that|it)|leave it|don'?t (?:do|bother)(?: (?:it|that))?)"
    r"(?: (?:please|thanks|thank you))?$"
)


def says_cancel(question: str) -> bool:
    """Whether the message is only a way of saying "drop that"."""
    low = " ".join(str(question or "").lower().replace("’", "'").split()).strip(" .!?,")
    return len(low) <= 40 and _CANCEL.match(low) is not None


def reply(question: str, history: list[dict]) -> list[dict] | None:
    """The events that drop the open card, or None when no card waits or the
    message says something else."""
    pending = Dialogue.from_history(history).pending_act
    if not pending or not says_cancel(question):
        return None
    what = pending[:1].lower() + pending[1:]
    return [
        {"type": "answer", "delta": f"Cancelled: {what.rstrip('.')}. Nothing was changed."},
        {"type": "act", "cancel": True},
    ]
