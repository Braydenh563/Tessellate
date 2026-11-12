"""Link properties on a link touching a private note are sealed like its reason.

Props are up to 20 short values a person wrote about the two notes, so they
follow the note (sweep 1004, found-not-fixed 1; GRAPH_PLAN KG decisions):
ciphertext at rest, a dict while the vault is open, None while it is locked.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from tessellate.core import crypto, vault
from tessellate.core.database import EntryLink
from tessellate.entry import manager_private

SECRET = "Dr Weatherby"
PROPS = {"doctor": SECRET, "count": 4}


@pytest.fixture(autouse=True)
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _raw(session):
    return session.execute(text("SELECT props FROM entry_links")).scalar()


def _note(client, content):
    return client.post("/entries", json={"content": content}).json()


def _private_note(client, content):
    note = _note(client, content)
    client.post(f"/entries/{note['id']}/privacy", json={"private": True})
    return note


def test_props_on_a_new_link_to_a_private_note_are_encrypted(client, session):
    public = _note(client, "buy milk")
    private = _private_note(client, "appointment notes")
    body = client.post(
        f"/entries/{public['id']}/links", json={"target_id": private["id"], "props": PROPS}
    ).json()
    assert SECRET not in _raw(session)
    assert crypto.PREFIX in _raw(session)
    assert body["links"][0]["props"] == PROPS
    assert client.get(f"/entries/{public['id']}").json()["links"][0]["props"] == PROPS


def test_a_locked_vault_reads_no_props(client, session):
    public = _note(client, "buy milk")
    private = _private_note(client, "appointment notes")
    client.post(f"/entries/{public['id']}/links", json={"target_id": private["id"], "props": PROPS})
    link_id = session.execute(text("SELECT id FROM entry_links")).scalar()
    vault.close()
    session.expire_all()
    assert session.get(EntryLink, link_id).props is None


def test_patching_props_on_a_private_link_stays_encrypted(client, session):
    a = _note(client, "buy milk")
    b = _private_note(client, "appointment notes")
    link = client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]}).json()["links"][0]
    out = client.patch(f"/entries/{a['id']}/links/{link['link_id']}", json={"props": PROPS}).json()
    assert out["links"][0]["props"] == PROPS
    assert SECRET not in _raw(session)
    cleared = client.patch(f"/entries/{a['id']}/links/{link['link_id']}", json={"props": {}}).json()
    assert cleared["links"][0]["props"] is None


def test_making_a_note_private_seals_and_public_again_restores(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "appointment notes")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"], "props": PROPS})
    assert json.loads(_raw(session)) == PROPS
    client.post(f"/entries/{b['id']}/privacy", json={"private": True})
    assert SECRET not in _raw(session)
    assert client.get(f"/entries/{a['id']}").json()["links"][0]["props"] == PROPS
    client.post(f"/entries/{b['id']}/privacy", json={"private": False})
    assert json.loads(_raw(session)) == PROPS


def test_rotating_the_key_moves_props(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "appointment notes")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"], "props": PROPS})
    client.post(f"/entries/{b['id']}/privacy", json={"private": True})
    before = _raw(session)
    old, new = vault.key(), crypto.new_dek()
    manager_private.rekey_private_extras(session, old, new)
    session.commit()
    vault.set_key(new)
    session.expire_all()
    assert _raw(session) != before
    assert session.query(EntryLink).one().props == PROPS


def test_a_public_link_keeps_plain_props(client, session):
    a = _note(client, "buy milk")
    b = _note(client, "pay rent")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"], "props": PROPS})
    assert json.loads(_raw(session)) == PROPS
