"""Audit 1031 N3, N23, N40: one private-note rule for every reference.

A private note's words show in its own row and editor and nowhere else. Any
other note that points at it (a link chip, the Connections sheet, the near
duplicate line) calls it "Private note", whether the vault is open or locked,
so the person never sees one note named by its text in one place and masked in
the next. The search never indexed private notes; the `[[` picker leaves them
out; the rail masks them. The rule is one constant, `manager.PRIVATE_LABEL`.
"""

from __future__ import annotations

import pytest

from tessellate.core import vault
from tessellate.entry import manager


@pytest.fixture
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _linked_pair(client):
    public = client.post("/entries", json={"content": "Weekly plan"}).json()
    secret = client.post("/entries", json={"content": "SECRET diary line"}).json()
    client.post(f"/entries/{public['id']}/links", json={"target_id": secret["id"]})
    marked = client.post(f"/entries/{secret['id']}/privacy", json={"private": True})
    assert marked.status_code == 200, marked.text
    return public, secret


def test_the_label_is_one_constant():
    assert manager.PRIVATE_LABEL == "Private note"


def test_a_link_chip_masks_a_private_target_with_the_vault_open(ai_client, open_vault):
    public, secret = _linked_pair(ai_client)
    links = ai_client.get(f"/entries/{public['id']}").json()["links"]
    assert [link["preview"] for link in links] == [manager.PRIVATE_LABEL]
    assert "SECRET" not in str(links)


def test_connections_and_chips_say_the_same_thing(ai_client, open_vault):
    public, secret = _linked_pair(ai_client)
    chip = ai_client.get(f"/entries/{public['id']}").json()["links"][0]["preview"]
    sheet = ai_client.get(f"/entries/{public['id']}/connections").json()["outgoing"][0]["preview"]
    assert chip == sheet == manager.PRIVATE_LABEL
