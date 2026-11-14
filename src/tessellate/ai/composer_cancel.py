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
    r"^(?:(?:ok|okay|actually|no|nah|oh|hmm|um|please|just|wait) )*"
    r"(?:cancel(?: (?:that|it|this|the (?:change|card|act)))?|undo(?: (?:that|it|this))?|never ?mind(?: (?:that|it))?|forget (?:it|that|about it)|scrap (?:that|it)|leave it|don'?t (?:do|bother)(?: (?:it|that))?)"
    r"(?: (?:please|thanks|thank you))?$"
)


def says_cancel(question: str) -> bool:
    """Whether the message is only a way of saying "drop that"."""
    #: Marks inside the message ("no, cancel that") are blanks: only the words are read.
    low = " ".join(re.sub(r"[,.;:!?]+", " ", str(question or "").lower().replace("’", "'")).split())
    return len(low) <= 40 and _CANCEL.match(low) is not None


#: "undo", "undo that", "take that back" (C13): the control that replays the last confirmed card's inverse.
_UNDO = re.compile(r"^(?:(?:ok|okay|actually|please|oh|wait) )*(?:undo(?: (?:that|it|this|the last (?:one|change|thing)))?|take (?:that|it) back|revert (?:that|it))(?: please)?$")


def undo_reply(session, question: str, history: list[dict]) -> list[dict] | None:  # noqa: ANN001
    """"undo that" after a confirmed card runs its stored inverse steps, once; None for anything else
    (a card still waiting is cancelled by `reply`, and with nothing to take back the help line answers)."""
    from tessellate.ai import acts, consent_store

    low = " ".join(re.sub(r"[,.;:!?]+", " ", str(question or "").lower().replace("’", "'")).split())
    if Dialogue.from_history(history).pending_act or not _UNDO.match(low):
        return None
    label, steps = consent_store.take_latest()
    done = acts.run(session, steps, []) if steps else None
    if done is None or not done["ok"]:
        return None
    return [{"type": "answer", "delta": f"Undone: {label[:1].lower()}{label[1:].rstrip('.')}."}]


def reply(question: str, history: list[dict]) -> list[dict] | None:
    """The events that drop the open card, or None when no card waits or the
    message says something else."""
    pending = Dialogue.from_history(history).pending_act
    if not pending or not says_cancel(question):
        return None
    what = pending[:1].lower() + pending[1:]
    return [
        {"type": "answer", "delta": f"Cancelled: {what.rstrip('.')}. Nothing was changed."},
        {"type": "act", "cancel": True, "label": pending},
    ]
