"""INBOX 1747: transitions the implicit state machines had no answer for.

One test per Reproduced row of docs/roadmap/agent-remaining/sm-1111.md."""

from __future__ import annotations

from tests.test_composer_route_688 import _ask
from tests.test_consent_1110 import _card, _count, _notebook, _waiting


def test_confirm_after_a_typed_yes_spent_the_card_runs_nothing_twice(client, session):
    """Consent card: open, spent by a typed yes, then Confirm pressed (a second tab, a reloaded
    transcript). The id is gone, and the route used to fall back to the steps the page sends,
    so the note was made twice."""
    _notebook(session)
    first = _ask(client, "note: buy stamps")
    card = _card(first)
    _ask(client, "yes", history=_waiting(first, card))
    assert _count(session, "buy stamps") == 1
    pressed = client.post("/chat/command/run", json={"steps": card["steps"], "consent_id": card["consent_id"]})
    assert pressed.status_code == 409
    assert _count(session, "buy stamps") == 1


def test_a_binned_note_cannot_be_archived_or_unarchived(client):
    """Note: live, archived, binned. Archiving a note already in the bin (a stale card in a second
    tab) made it binned and archived, so Restore brought it back into the Archive, out of sight."""
    nid = client.post("/entries", json={"content": "alpha body"}).json()["id"]
    client.delete(f"/entries/{nid}")
    archived = client.post(f"/entries/{nid}/archive")
    unarchived = client.post(f"/entries/{nid}/unarchive")
    assert (archived.status_code, unarchived.status_code) == (409, 409)
    restored = client.post(f"/entries/{nid}/restore").json()
    assert not restored["archived_at"]


def test_a_live_note_cannot_be_linked_to_a_binned_one(client):
    """Note: link to a binned note. The link route, and the tension accept route that makes the
    same kind of link, answered 200 and left an edge to an invisible note until purge."""
    live = client.post("/entries", json={"content": "alpha body"}).json()["id"]
    other = client.post("/entries", json={"content": "beta body"}).json()["id"]
    gone = client.post("/entries", json={"content": "gamma body"}).json()["id"]
    client.delete(f"/entries/{gone}")
    refused = client.post(f"/entries/{live}/links", json={"target_id": gone})
    forward = client.post("/entries/tensions/accept", json={"earlier_id": live, "later_id": gone})
    backward = client.post("/entries/tensions/accept", json={"earlier_id": gone, "later_id": live})
    assert (refused.status_code, forward.status_code, backward.status_code) == (409, 409, 409)
    held = client.get(f"/entries/{live}").json()
    assert held["links"] == []
    fine = client.post(f"/entries/{live}/links", json={"target_id": other})
    assert fine.status_code == 200


def test_a_second_complete_of_the_same_occurrence_does_not_skip_one(client):
    """Recurring reminder: two Completes (double-click, two tabs) used to roll the rule twice, so
    an occurrence went unseen. With `expected_due_at` the second one answers 409, rolled once."""
    made = client.post("/reminders", json={"text": "Water plants", "due_at": "2030-01-25T12:30:00Z",
                                           "recurring": "FREQ=DAILY"}).json()
    seen = made["due_at"]
    first = client.post(f"/reminders/{made['id']}/complete", params={"expected_due_at": seen})
    second = client.post(f"/reminders/{made['id']}/complete", params={"expected_due_at": seen})
    assert (first.status_code, second.status_code) == (200, 409)
    listed = {r["id"]: r for r in client.get("/reminders").json()}
    assert listed[made["id"]]["due_at"][:19] == first.json()["due_at"][:19] == "2030-01-26T12:30:00"
    # No expected time sent: the old unconditional roll stays for callers that do not know it.
    again = client.post(f"/reminders/{made['id']}/complete")
    assert again.status_code == 200


def test_typed_words_are_kept_sealed_across_a_lock_and_handed_back(client):
    """Lock screen and the unsaved words: the fields are sealed with the vault key (never plain on
    disk), unreadable once the key is gone, and handed back after the next unlock."""
    from tessellate.core import crypto, deps, vault

    config = deps.get_config()
    vault.set_key(crypto.new_dek())
    try:
        sent = {"entry-content": "my half written secret", "entry-title": "", "question": "who is?"}
        kept = client.put("/kept-words", json={"fields": sent}).json()
        assert kept == {"kept": 2}
        assert b"half written" not in (config.data_dir / "kept-words.enc").read_bytes()
        got = client.get("/kept-words").json()
        assert got["fields"] == {"entry-content": "my half written secret", "question": "who is?"}
        key = vault.key()
        vault.close()
        refused = client.put("/kept-words", json={"fields": sent})
        sealed = client.get("/kept-words").json()
        assert (refused.status_code, sealed["fields"]) == (409, {})
        vault.set_key(key)
        back = client.get("/kept-words").json()
        assert back["fields"]["question"] == "who is?"
        gone = client.delete("/kept-words")
        assert gone.status_code == 204
        after = client.get("/kept-words").json()
        assert after["fields"] == {}
    finally:
        vault.close()


def test_lock_seals_the_typed_fields_before_it_locks_and_every_listed_id_exists():
    """The lock keeps the typed words first (`keepTypedWords`), then locks; each id the list names
    is a real field (a renamed id would quietly keep nothing), and the stand-in knows the names."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    unlock = (root / "js" / "vault-unlock.js").read_text(encoding="utf-8")
    ids = re.findall(r'"([a-z][a-z-]+)"', re.search(r"const TYPED_IDS = \[(.*?)\];", unlock, re.S).group(1))
    ids += re.findall(r'"([a-z][a-z-]+)"', re.search(r"const SEARCH_ONLY_IDS = \[(.*?)\];", unlock, re.S).group(1))
    everything = (root / "index.html").read_text(encoding="utf-8") + "".join(
        p.read_text(encoding="utf-8") for p in (root / "js").glob("*.js")
    )
    missing = [i for i in ids if f'id="{i}"' not in everything and f'"{i}"' not in everything.replace(unlock, "")]
    assert len(ids) > 40 and not missing, missing
    app = (root / "js" / "app.js").read_text(encoding="utf-8")
    lock = app[app.index("async function lockNow()"):]
    assert lock.index('typedWords("keep")') < lock.index('"/auth/lock"')
    assert '"ensureVaultOpen", "typedWords"' in app
    # Row 26: the edit form's two fields are marked so the lock empties them wherever the form is
    # drawn, the dashboard's note titles are purged, and the kept edit leaves this browser.
    panels = (root / "js" / "note-edit-panels.js").read_text(encoding="utf-8")
    assert panels.count('.dataset.holdsNotebook = ""') == 2
    assert '"dash-glance"' in app and '"dash-more"' in app
    assert 'prefs.remove(EDIT_DRAFT)' in unlock
    # Row 19: the lock stops a running stream and drops the open conversation's turns from memory.
    purge = app[app.index("function purgeLockedContent()"):app.index("async function lockNow()")]
    assert "chatController?.abort()" in purge and "chatConv = { id: null, turns: [] }" in purge


def test_a_notification_snooze_does_not_reopen_a_done_reminder(client):
    """Reminder: snooze of a done one. A notification left on screen after the reminder was ticked
    off set it open again on its Snooze press; it answers ok and changes nothing."""
    made = client.post("/reminders", json={"text": "Call Sam", "due_at": "2030-01-25T12:30:00Z"}).json()
    minted = client.post(f"/reminders/{made['id']}/notification-token").json()
    ticked = client.put(f"/reminders/{made['id']}", json={"done": True})
    assert ticked.json()["done"] is True
    body = {"token": minted["token"], "action": "snooze"}
    snoozed = client.post(f"/reminders/{made['id']}/notification-act", json=body)
    assert snoozed.status_code == 200
    listed = {r["id"]: r for r in client.get("/reminders").json()}
    assert listed[made["id"]]["done"] is True
    assert listed[made["id"]]["due_at"][:19] == "2030-01-25T12:30:00"


def test_a_board_does_not_draw_a_card_for_a_binned_note(client):
    """Whiteboard and its linked notes: a card whose note went to the bin stayed on the board and
    opened a note nobody could see. It is hidden while binned and comes back with Restore."""
    kept = client.post("/entries", json={"content": "alpha body"}).json()["id"]
    gone = client.post("/entries", json={"content": "beta body"}).json()["id"]
    for note in (kept, gone):
        placed = client.post("/whiteboard/nodes", json={"entry_id": note, "x": 10, "y": 10})
        assert placed.status_code == 200, placed.text
    client.delete(f"/entries/{gone}")
    shown = [n["entry_id"] for n in client.get("/whiteboard/").json()["nodes"]]
    assert shown == [kept]
    client.post(f"/entries/{gone}/restore")
    again = sorted(n["entry_id"] for n in client.get("/whiteboard/").json()["nodes"])
    assert again == sorted([kept, gone])


def test_a_refused_complete_says_where_the_reminder_is_now(client):
    """The bell row's Done sends the occurrence it was raised for; ticked elsewhere since, the 409
    carries the reminder as it is now, so the row can say "Already done, next ..." (review on #222)."""
    made = client.post("/reminders", json={"text": "Water plants", "due_at": "2030-01-25T12:30:00Z",
                                           "recurring": "FREQ=DAILY"}).json()
    client.post(f"/reminders/{made['id']}/complete", params={"expected_due_at": made["due_at"]})
    late = client.post(f"/reminders/{made['id']}/complete", params={"expected_due_at": made["due_at"]})
    assert late.status_code == 409
    detail = late.json()["detail"]
    assert detail["message"] == "That reminder already moved on. Reload to see it."
    assert detail["reminder"]["id"] == made["id"] and detail["reminder"]["due_at"][:19] == "2030-01-26T12:30:00"
