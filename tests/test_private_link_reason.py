"""A link reason on a link touching a private note is not stored in the clear.

The reason is a sentence about the two notes ("both are about my diagnosis"),
so it follows the note's content: ciphertext at rest, plain text while the
vault is open, absent from the activity log's text. Tags stay visible by
decision (docs/ARCHITECTURE.md, privacy notes); the last test pins that.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tessellate.core import crypto, vault
from tessellate.core.database import AuditLog, Entry, EntryLink, EntryRevision
from tessellate.entry import manager_private

SECRET = "named after my oncologist, Dr Weatherby"


@pytest.fixture(autouse=True)
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _raw_reason(session):
    return session.execute(text("SELECT reason FROM entry_links")).scalar()


def _db_dump(session) -> str:
    """The links table and every audit row as one string, to grep for the secret."""
    rows = [str(r) for r in session.execute(text("SELECT * FROM entry_links")).all()]
    rows += [str(r) for r in session.execute(text("SELECT detail, payload FROM audit_log")).all()]
    return "\n".join(rows)


def _note(client, content):
    return client.post("/entries", json={"content": content}).json()


def _private_note(client, content):
    note = _note(client, content)
    client.post(f"/entries/{note['id']}/privacy", json={"private": True})
    return note


def test_a_reason_on_a_new_link_to_a_private_note_is_encrypted(client, session):
    public = _note(client, "buy milk")
    private = _private_note(client, "appointment notes")

    body = client.post(
        f"/entries/{public['id']}/links", json={"target_id": private["id"], "reason": SECRET}
    ).json()

    assert crypto.is_encrypted(_raw_reason(session))
    assert "Weatherby" not in _db_dump(session)
    # Unlocked, the person still reads it.
    assert body["links"][0]["reason"] == SECRET
    assert client.get(f"/entries/{public['id']}").json()["links"][0]["reason"] == SECRET


def test_a_locked_vault_shows_no_reason_rather_than_ciphertext(client, session):
    public = _note(client, "buy milk")
    private = _private_note(client, "appointment notes")
    client.post(
        f"/entries/{public['id']}/links", json={"target_id": private["id"], "reason": SECRET}
    )
    link_id = session.execute(text("SELECT id FROM entry_links")).scalar()
    vault.close()
    session.expire_all()

    assert session.get(EntryLink, link_id).reason is None


def test_making_a_linked_note_private_seals_its_existing_reason_and_log(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "appointment notes")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"], "reason": SECRET})
    assert _raw_reason(session) == SECRET  # a public pair: plain, as before
    assert "Weatherby" in _db_dump(session)

    client.post(f"/entries/{b['id']}/privacy", json={"private": True})

    assert crypto.is_encrypted(_raw_reason(session))
    assert "Weatherby" not in _db_dump(session)
    assert client.get(f"/entries/{a['id']}").json()["links"][0]["reason"] == SECRET


def test_making_it_public_again_restores_the_plain_reason(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "appointment notes")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"], "reason": SECRET})
    client.post(f"/entries/{b['id']}/privacy", json={"private": True})
    client.post(f"/entries/{b['id']}/privacy", json={"private": False})
    assert _raw_reason(session) == SECRET


def test_a_reason_stays_sealed_while_the_other_end_is_still_private(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "appointment notes")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"], "reason": SECRET})
    client.post(f"/entries/{a['id']}/privacy", json={"private": True})
    client.post(f"/entries/{b['id']}/privacy", json={"private": True})
    client.post(f"/entries/{a['id']}/privacy", json={"private": False})
    assert crypto.is_encrypted(_raw_reason(session))


def test_editing_a_reason_on_a_private_link_stays_encrypted(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "appointment notes")
    link = client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]}).json()["links"][0]
    client.post(f"/entries/{b['id']}/privacy", json={"private": True})

    out = client.put(
        f"/entries/{a['id']}/links/{link['link_id']}/reason", json={"reason": SECRET}
    ).json()

    assert out["links"][0]["reason"] == SECRET
    assert crypto.is_encrypted(_raw_reason(session))
    assert "Weatherby" not in _db_dump(session)


def test_a_public_link_is_untouched(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "pay rent")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"], "reason": SECRET})
    assert _raw_reason(session) == SECRET


def test_rotating_the_key_moves_reasons_history_and_payloads(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "appointment notes")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"], "reason": SECRET})
    client.put(f"/entries/{b['id']}", json={"content": "appointment notes, second draft"})
    client.post(f"/entries/{b['id']}/privacy", json={"private": True})
    before = _raw_reason(session)

    old, new = vault.key(), crypto.new_dek()
    manager_private.rekey_private_extras(session, old, new)
    session.commit()
    vault.set_key(new)
    session.expire_all()

    after = _raw_reason(session)
    assert after != before
    assert crypto.decrypt(new, after) == SECRET
    revisions = session.query(EntryRevision).filter_by(entry_id=b["id"]).all()
    assert revisions
    for revision in revisions:
        assert crypto.decrypt(new, revision.content)  # opens under the new key
    opened = 0
    for row in session.query(AuditLog).filter(AuditLog.payload.is_not(None)):
        for state in ((row.payload or {}).get(side) or {} for side in ("before", "after")):
            for name in ("content", "reason"):
                if isinstance(state.get(name), str) and crypto.is_encrypted(state[name]):
                    crypto.decrypt(new, state[name])
                    opened += 1
    assert opened


def test_tags_stay_visible_on_a_private_note_by_decision(client, session):
    """The list shows a private note's tags by design (ARCHITECTURE.md, privacy
    notes), so `entries.tags` and `entry_revisions.tags` are plain text and
    only the content is ciphertext. This pins the decision."""
    note = client.post("/entries", json={"content": "lab results", "tags": ["health"]}).json()
    client.put(f"/entries/{note['id']}", json={"content": "lab results v2", "tags": ["health"]})
    client.post(f"/entries/{note['id']}/privacy", json={"private": True})

    entry = session.get(Entry, note["id"])
    assert crypto.is_encrypted(entry.content)
    assert "health" in entry.tags
    revisions = session.query(EntryRevision).filter_by(entry_id=note["id"]).all()
    assert revisions and all(crypto.is_encrypted(r.content) for r in revisions)
    assert any("health" in r.tags for r in revisions)
