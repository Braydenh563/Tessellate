"""Consent for every act (the owner, 2026-11-10: "any and all actions need the
user's consent"): a typed yes or no to the card that waits.

Every act the composer or the model proposes is a card with Confirm and Cancel
and changes nothing until one is pressed or the person types their consent in
any wording. The server keeps no conversation, so the page says which card is
open: the turn before carries `pending_act` (its label) and the steps or the
tool call Confirm would run (`ChatTurn`), only while the card waits. A reply
applies to that one card and no other; with nothing waiting these words are not
read here at all ("yes" is then an offer's answer, `composer_talk`).
`api/chat_agent.consent_events` does the running.
"""

from __future__ import annotations

import re

#: What a yes is made of. A message is consent when, after the fillers are
#: dropped, it is only these (so "yes please" and "ok go ahead" are, and "yes
#: but only the first one" is not).
_YES_WORDS = (
    r"yes|yeah|yep|yup|ya|yea|sure|ok|okay|alright|all right|do it|do that|go ahead|go for it|please do|sounds good|that works|"
    r"confirm|confirmed|absolutely|definitely|of course|affirmative|fine|why not|go on|make it so|proceed"
)
_NO_WORDS = (
    r"no|nope|nah|cancel|don'?t|do not|never ?mind|stop|forget (?:it|that|about it)|leave it|scrap (?:that|it)|not now|"
    r"don'?t do (?:it|that)|do not do (?:it|that)|no thanks|no thank you"
)
_FILLER = re.compile(r"\b(?:please|thanks|thank you|then|now|oh|well|so|um|hmm|actually|just|wait)\b")
_YES = re.compile(rf"^(?:(?:{_YES_WORDS})(?: |$))+$")
_NO = re.compile(rf"^(?:(?:{_NO_WORDS})(?: |$))+$")


def _words(question: str) -> str:
    low = str(question or "").lower().replace("’", "'")
    return " ".join(re.sub(r"[,.;:!?]+", " ", low).split())


def says(question: str) -> str | None:
    """"yes" or "no" when the whole message is a consent or a refusal, else None."""
    low = _words(question)
    if not low or len(low) > 40:
        return None
    if _NO.match(low):
        return "no"
    plain = " ".join(_FILLER.sub(" ", low).split())
    if plain and _NO.match(plain):
        return "no"
    return "yes" if _YES.match(low) or (plain and _YES.match(plain)) else None


def read(question: str, history: list[dict] | None) -> dict | None:
    """The reply to the card the last turn left waiting: `{verdict, label, steps,
    skipped, tool}`, or None when no card waits or the message is not a consent
    or a refusal. A consent only ever reaches the card of the turn just before."""
    last = (history or [{}])[-1] if history else {}
    label = str(last.get("pending_act") or "").strip()
    verdict = says(question) if label else None
    if verdict is None:
        return None
    return {
        "verdict": verdict, "label": label, "steps": last.get("pending_steps") or [],
        "skipped": last.get("pending_skipped") or [], "tool": last.get("pending_tool") or None,
    }
