"""A reopened chat draws a turn's act card again (owner: "the yellow notice of an action performed
didnt stay persistent in the chat session after I left and came back").

The turn saves the card it showed (`acts`); the reader recounts its state from the server's parked
card (`consent_store`), never from the page: waiting while the card is still parked, its settled
outcome once answered, expired when the server no longer knows it. Confirm on an expired id runs
nothing (the page's steps are not trusted once the parked card is gone)."""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import consent_store
from tessellate.api.routes_conversations import _hydrate_acts, _saved_acts

ROOT = Path(__file__).resolve().parent.parent
STEPS = [{"name": "pin_note", "arguments": {"note_id": 1}}]


def _turn(client, **card):
    base = {"type": "act", "label": "Pin the dentist note", "steps": STEPS, "skipped": [], "notice": "Pin it?"}
    created = client.post("/conversations", json={"question": "pin it", "answer": "Pin one note. Confirm or Cancel below.", "acts": [{**base, **card}]}).json()
    return created["id"]


def _acts(client, cid):
    return client.get(f"/conversations/{cid}").json()["messages"][1]["acts"]


def test_a_waiting_card_is_saved_and_reads_pending(client):
    consent_store.reset_for_tests()
    key = consent_store.park({"label": "Pin the dentist note", "steps": STEPS, "skipped": []})
    cid = _turn(client, consent_id=key)
    card = _acts(client, cid)[0]
    assert card["state"] == "pending" and card["consent_id"] == key and card["steps"] == STEPS


def test_an_unknown_or_old_card_reads_expired(client):
    consent_store.reset_for_tests()
    cid = _turn(client, consent_id="gone")
    assert _acts(client, cid)[0]["state"] == "expired"


def test_a_card_spent_elsewhere_reads_done(client):
    consent_store.reset_for_tests()
    key = consent_store.park({"label": "x", "steps": STEPS, "skipped": []})
    cid = _turn(client, consent_id=key)
    consent_store.take(key)
    assert _acts(client, cid)[0]["state"] == "done"


def test_cancel_is_saved_and_spends_the_card(client):
    consent_store.reset_for_tests()
    key = consent_store.park({"label": "x", "steps": STEPS, "skipped": []})
    cid = _turn(client, consent_id=key)
    put = client.put(f"/conversations/{cid}/turns/0/acts/0", json={"outcome": "cancelled", "consent_id": key, "label": "Pin the dentist note"})
    assert put.status_code == 200
    assert _acts(client, cid)[0]["state"] == "cancelled"
    assert consent_store.peek(key) is None


def test_confirm_is_saved_with_its_undo(client):
    client.post("/entries", json={"content": "Dentist", "category": "General"})
    key = _parked()
    cid = _turn(client, consent_id=key)
    assert _press(client, key).status_code == 200  # the run keeps what it did under the card's id
    body = {"consent_id": key, "label": "Pin the dentist note"}
    client.put(f"/conversations/{cid}/turns/0/acts/0", json={"outcome": "done", **body})
    card = _acts(client, cid)[0]
    assert card["state"] == "done" and card["summary"] and card["undo"]
    client.put(f"/conversations/{cid}/turns/0/acts/0", json={"outcome": "undone", **body})
    assert _acts(client, cid)[0]["state"] == "undone"


def test_a_missing_turn_or_card_is_a_no_op(client):
    consent_store.reset_for_tests()
    cid = _turn(client, consent_id="k")
    assert client.put(f"/conversations/{cid}/turns/5/acts/0", json={"outcome": "cancelled"}).json() == {"saved": False}
    assert client.put(f"/conversations/{cid}/turns/0/acts/3", json={"outcome": "cancelled"}).json() == {"saved": False}


def test_a_card_that_ran_at_once_keeps_its_undo(client):
    cid = _turn(client, done=True, summary="Done.", undo=[{"name": "unpin_note", "arguments": {"note_id": 1}}])
    assert _acts(client, cid)[0]["state"] == "done"


def test_confirm_with_an_expired_id_runs_nothing(client):
    consent_store.reset_for_tests()
    run = client.post("/chat/command/run", json={"steps": STEPS, "consent_id": "expired-key"})
    assert run.status_code == 409


def test_the_reopen_path_redraws_the_card():
    kit = (ROOT / "frontend/js/sheets-selects.js").read_text(encoding="utf-8")
    assert "renderToolConfirm.saved(handles, message)" in kit
    assert "renderToolConfirm(act.type" in (ROOT / "frontend/js/answer-kit.js").read_text(encoding="utf-8")
    card = (ROOT / "frontend/js/ask-compose.js").read_text(encoding="utf-8")
    assert "event.notice" in card and "offer.notice" in card
    assert "This offer has expired. Ask again to redo it." in (ROOT / "src/tessellate/api/routes_conversations.py").read_text(encoding="utf-8")


# --- the saved outcome is the server's reading, never the page's ------------------------------


def _press(client, key):
    """Confirm on a parked act as the page does: the run spends the card and keeps its result."""
    return client.post("/chat/command/run", json={"steps": STEPS, "consent_id": key})


def _put(client, cid, **body):
    return client.put(f"/conversations/{cid}/turns/0/acts/0", json=body)


def _parked(label="Pin the dentist note"):
    consent_store.reset_for_tests()
    return consent_store.park({"label": label, "steps": STEPS, "skipped": []})


def test_done_cannot_be_forged_for_a_waiting_card(client):
    key = _parked()
    cid = _turn(client, consent_id=key)
    forged = _put(client, cid, outcome="done", consent_id=key, label="Pin the dentist note", summary="Done.", undo=[{"name": "delete_note", "arguments": {"note_id": 9}}])
    assert forged.status_code == 409
    card = _acts(client, cid)[0]
    assert card["state"] == "pending" and not card.get("undo")


def test_done_takes_the_servers_result_not_the_pages(client):
    key = _parked()
    cid = _turn(client, consent_id=key)
    consent_store.take(key)
    consent_store.remember(key, {"summary": "Done: pinned.", "undo": [{"name": "unpin_note", "arguments": {"note_id": 1}}]})
    assert _put(client, cid, outcome="done", consent_id=key, label="Pin the dentist note", summary="forged", undo=[{"name": "x"}]).status_code == 200
    card = _acts(client, cid)[0]
    assert (card["state"], card["summary"], card["undo"][0]["name"]) == ("done", "Done: pinned.", "unpin_note")


def test_a_pressed_card_reads_done_even_if_its_outcome_never_arrived(client):
    key = _parked()
    cid = _turn(client, consent_id=key)
    consent_store.take(key)
    consent_store.remember(key, {"summary": "Done: pinned.", "undo": []})
    assert _acts(client, cid)[0]["state"] == "done"


def test_an_answered_card_does_not_flip(client):
    key = _parked()
    cid = _turn(client, consent_id=key)
    assert _put(client, cid, outcome="cancelled", consent_id=key, label="Pin the dentist note").status_code == 200
    again = _put(client, cid, outcome="done", consent_id=key, label="Pin the dentist note")
    assert again.status_code == 409 and _acts(client, cid)[0]["state"] == "cancelled"
    key2 = _parked()
    cid2 = _turn(client, consent_id=key2)
    consent_store.take(key2)
    consent_store.remember(key2, {"summary": "Done.", "undo": []})
    _put(client, cid2, outcome="done", consent_id=key2, label="Pin the dentist note")
    assert _put(client, cid2, outcome="cancelled", consent_id=key2, label="Pin the dentist note").status_code == 409
    assert _put(client, cid2, outcome="undone", consent_id=key2, label="Pin the dentist note").status_code == 200
    assert _acts(client, cid2)[0]["state"] == "undone"
    assert _put(client, cid2, outcome="done", consent_id=key2, label="Pin the dentist note").status_code == 409


def test_more_than_six_cards_are_cut_not_refused(client):
    consent_store.reset_for_tests()
    cards = [{"type": "act", "label": f"Pin {i}", "steps": STEPS, "consent_id": f"k{i}"} for i in range(9)]
    made = client.post("/conversations", json={"question": "q", "answer": "a", "acts": cards})
    assert made.status_code == 200 or made.status_code == 201
    assert len(_acts(client, made.json()["id"])) == 6


def test_an_outcome_for_another_card_is_refused(client):
    first = _parked()
    cid = _turn(client, consent_id=first)
    other = consent_store.park({"label": "Other", "steps": STEPS, "skipped": []})
    wrong = _put(client, cid, outcome="cancelled", consent_id=other, label="Other")
    assert wrong.status_code == 409
    assert consent_store.peek(other) is not None and consent_store.peek(first) is not None
    assert _put(client, cid, outcome="cancelled", consent_id=first, label="Pin the dentist note").status_code == 200


def _tool_card(key):
    return {"type": "confirm", "name": "delete_note", "arguments": {"note_id": 1}, "label": "Delete the note", "consent_id": key}


def _tool_turn(client, key):
    return client.post("/conversations", json={"question": "q", "answer": "a", "acts": [_tool_card(key)]}).json()["id"]


def test_a_tool_confirm_card_is_saved_and_reads_pending_then_expired(client):
    consent_store.reset_for_tests()
    key = consent_store.park({"label": "Delete the note", "tool": {"name": "delete_note", "arguments": {"note_id": 1}}})
    cid = _tool_turn(client, key)
    card = _acts(client, cid)[0]
    assert (card["type"], card["state"], card["name"], card["arguments"]) == ("confirm", "pending", "delete_note", {"note_id": 1})
    consent_store.reset_for_tests()
    assert _acts(client, cid)[0]["state"] == "expired"


def test_a_pressed_tool_card_reads_done_from_the_servers_result(client):
    consent_store.reset_for_tests()
    note = client.post("/entries", json={"content": "delete me", "category": "Junk"}).json()
    args = {"note_id": note["id"]}
    key = consent_store.park({"label": "Delete the note", "tool": {"name": "delete_note", "arguments": args}})
    cid = client.post("/conversations", json={"question": "q", "answer": "a", "acts": [{**_tool_card(key), "arguments": args}]}).json()["id"]
    ran = client.post("/chat/tools/execute", json={"name": "delete_note", "arguments": args, "consent_id": key})
    assert ran.status_code == 200
    card = _acts(client, cid)[0]
    assert card["state"] == "done" and card["summary"] == ran.json()["label"]
    assert client.post("/chat/tools/execute", json={"name": "delete_note", "arguments": args, "consent_id": key}).status_code == 409


def _offer(**extra):
    return {"type": "offer", "offer": {"kind": "note", "label": "Gather them into one note", "line": "Gather them into one note?", "text": "# Gathered\n\nbody"}, **extra}


def _offer_turn(client, **extra):
    return client.post("/conversations", json={"question": "q", "answer": "a", "acts": [_offer(**extra)]}).json()["id"]


def test_a_note_offer_is_saved_and_follows_its_parked_life(client):
    consent_store.reset_for_tests()
    key = consent_store.park({"label": "Gather them into one note", "offer": {"line": "x", "text": "t"}})
    cid = _offer_turn(client, consent_id=key)
    card = _acts(client, cid)[0]
    assert (card["type"], card["state"], card["offer"]["kind"]) == ("offer", "pending", "note")
    consent_store.reset_for_tests()
    assert _acts(client, cid)[0]["state"] == "expired"


def test_pressing_an_offer_is_saved_once_and_spends_it(client):
    consent_store.reset_for_tests()
    key = consent_store.park({"label": "Gather them into one note", "offer": {"line": "x", "text": "t"}})
    cid = _offer_turn(client, consent_id=key)
    body = {"consent_id": key, "label": "Gather them into one note"}
    assert _put(client, cid, outcome="done", summary="Saved a note: Gathered.", **body).status_code == 200
    card = _acts(client, cid)[0]
    assert (card["state"], card["summary"]) == ("done", "Saved a note: Gathered.")
    assert consent_store.peek(key) is None
    assert _put(client, cid, outcome="done", summary="again", **body).status_code == 200  # a repeat changes nothing
    assert _acts(client, cid)[0]["summary"] == "Saved a note: Gathered."
    assert _put(client, cid, outcome="undone", **body).status_code == 200
    assert _acts(client, cid)[0]["state"] == "undone"


def test_an_offer_with_no_parked_id_waits_until_pressed(client):
    cid = _offer_turn(client)
    assert _acts(client, cid)[0]["state"] == "pending"


def test_a_note_offer_goes_back_into_the_turns_support(client):
    consent_store.reset_for_tests()
    key = consent_store.park({"label": "Gather them into one note", "offer": {"line": "x", "text": "t"}})
    messages = [{"role": "assistant", "support": {"digest": True}, "acts": _saved_acts([_offer(consent_id=key)])}]
    _hydrate_acts(messages)
    offer = messages[0]["support"]["offer"]
    assert (offer["state"], offer["offer_id"], offer["act_slot"], offer["kind"]) == ("pending", key, 0, "note")


# --- a typed no is a decline, never a spent-and-done card -------------------------------------


def test_a_typed_no_reopens_as_cancelled_and_runs_nothing(client):
    from tessellate.api import chat_agent

    key = _parked()
    cid = _turn(client, consent_id=key)
    events = chat_agent.consent_events(None, {"id": key, "label": "Pin the dentist note", "verdict": "no"})
    assert any(e.get("cancel") for e in events)
    card = _acts(client, cid)[0]
    assert card["state"] == "cancelled" and card["notice"].startswith("Cancelled")
    assert _put(client, cid, outcome="done", consent_id=key, label="Pin the dentist note").status_code == 409
    assert _press(client, key).status_code == 409


def test_a_typed_yes_still_reads_done(client):
    key = _parked()
    cid = _turn(client, consent_id=key)
    consent_store.take(key)
    assert _acts(client, cid)[0]["state"] == "done"


def test_the_page_queues_an_outcome_pressed_before_its_turn_is_saved():
    kit = (ROOT / "frontend/js/answer-kit.js").read_text(encoding="utf-8")
    turn = (ROOT / "frontend/js/chat-turn.js").read_text(encoding="utf-8")
    assert "msg.saving" in kit and "msg.turnIndex" in kit
    assert "bubble.saving = []" in turn or ".saving = []" in turn
    assert "turnIndex = convRef.turns.length - 1" in turn and "saving.splice" in turn
