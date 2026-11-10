"""Consent for every act (the owner, 2026-11-10: "any and all actions need the
user's consent"): a typed yes or no to the card that waits.

Every act the composer or the model proposes is a card with Confirm and Cancel
and changes nothing until one is pressed or the person types their consent in
any wording. The server keeps no conversation, so the page says which card is
open: the turn before carries `pending_act` (its label) and `pending_id`
(`ChatTurn`), only while the card waits and only on the last assistant turn.
What a yes runs is what the server parked under that id when the card was
drawn (`consent_store`), never steps or arguments the page sends back. A reply
applies to that one card and no other; with nothing waiting these words are not
read here at all ("yes" is then an offer's answer, `composer_talk`).
`api/chat_agent.consent_events` does the running.
"""

from __future__ import annotations

import re

from tessellate.ai import consent_store

#: What a yes is made of. A message is consent when, after the fillers are
#: dropped, it is only these (so "yes please" and "ok go ahead" are, and "yes
#: but only the first one" is not).
_YES_WORDS = (
    r"yes|yeah|yep|yup|ya|yea|sure|ok|okay|do it|do that|go ahead|go for it|please do|sounds good|that works|"
    r"confirm|confirmed|absolutely|definitely|of course|affirmative|go on|make it so|proceed"
)
_NO_WORDS = (
    r"no|nope|nah|cancel|don'?t|do not|never ?mind|stop|forget (?:it|that|about it)|leave it|scrap (?:that|it)|not now|"
    r"don'?t do (?:it|that)|do not do (?:it|that)|no thanks|no thank you"
)
_FILLER = re.compile(r"\b(?:please|thanks|thank you|then|now|oh|well|so|um|hmm|actually|just)\b")
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


def _handoff_label(payload: dict) -> str:
    """What the page's "Run the skill" or "Run the plan" card is called (the label a typed reply names)."""
    if payload["type"] == "run_skill":
        return f"Run the skill “{payload.get('skill') or ''}”"
    return str(payload.get("goal") or "Run the plan")


def attach(payload: dict) -> dict:
    """`payload` as the page gets it: a card that waits (an act's, a parked
    tool call, or the page's own skill and plan card) is kept on the server and
    carries `consent_id`; `_say` (how the run is worded) stays on the server.
    Anything else passes unchanged."""
    if payload.get("type") in ("run_skill", "run_plan") and not payload.get("consented"):
        label = _handoff_label(payload)
        return {**payload, "ask_label": label, "consent_id": consent_store.park({"label": label, "handoff": dict(payload)})}
    if "_say" not in payload and payload.get("type") not in ("act", "confirm"):
        return payload
    out = dict(payload)
    say = out.pop("_say", None)
    if out.get("type") == "act" and out.get("steps") and not (out.get("done") or out.get("cancel") or out.get("settle")):
        out["consent_id"] = consent_store.park({"label": out.get("label") or "", "steps": out["steps"], "skipped": out.get("skipped") or [], "say": say})
    elif out.get("type") == "confirm" and out.get("name"):
        out["consent_id"] = consent_store.park({"label": out.get("label") or out["name"], "tool": {"name": out["name"], "arguments": out.get("arguments") or {}}})
    return out


def read(question: str, history: list[dict] | None) -> dict | None:
    """The reply to the card the last turn left waiting: `{verdict, label, id}`, or
    None when no card waits or the message is not a consent or a refusal. A
    consent only ever reaches the card of the last assistant turn."""
    last = (history or [{}])[-1] if history else {}
    label = str(last.get("pending_act") or "").strip()
    verdict = says(question) if label and str(last.get("answer") or "").strip() else None
    if verdict is None:
        return None
    return {"verdict": verdict, "label": label, "id": str(last.get("pending_id") or "")}
