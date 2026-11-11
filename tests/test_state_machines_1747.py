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
