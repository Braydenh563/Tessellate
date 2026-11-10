"""Pressing Confirm in a test (owner, 2026-11-10, "any and all actions need the user's
consent"): no act runs at once, so a test that checks what an act did first asks, then
presses Confirm as the page does (`POST /chat/command/run` with the card's steps).

`confirmed(client, events)` takes the events of a turn, as a list (`type` on each) or the
dict of lists `tests.test_composer_route_688._ask` gives, and returns the same shape with the
waiting card replaced by its done form: `done`, `summary`, `undo`, and the answer text said
as the summary. The card must not already be done: that is the at-once run the order removed.
"""

from __future__ import annotations


def _press(client, card: dict) -> dict:
    assert not card.get("done"), "an act ran before Confirm"
    response = client.post("/chat/command/run", json={"steps": card["steps"], "skipped": card.get("skipped") or []})
    assert response.status_code == 200, response.text
    result = response.json()
    return {**card, "notice": "", "done": True, "summary": result["summary"], "undo": result["undo"], "open": result.get("open")}


def confirmed(client, events):  # noqa: ANN001, ANN201
    if isinstance(events, dict):
        card = next((e for e in events.get("act", []) if not e.get("done") and not e.get("cancel")), None)
        if card is None:
            return events
        done = _press(client, card)
        return {**events, "act": [done], "answer": [{"type": "answer", "delta": done["summary"]}], "text": done["summary"]}
    card = next((e for e in events if e.get("type") == "act" and not e.get("done") and not e.get("cancel")), None)
    if card is None:
        return events
    done = _press(client, card)
    said = [{"type": "answer", "delta": done["summary"]}]
    return [done if e is card else e for e in events if e.get("type") != "answer"] + said
