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
    assert client.post(f"/entries/{nid}/archive").status_code == 409
    assert client.post(f"/entries/{nid}/unarchive").status_code == 409
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
