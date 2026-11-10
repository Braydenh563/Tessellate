"""W3 (1110): the vault side doors still open at the audit's last pass.

A11: a link to a private note was accepted by the API while the vault was
locked (the chip then carried the note's presence). A13: the vault open or
not, `/search` and `/entries/query` never return a private note.
"""

from __future__ import annotations

from tests.test_vault_read_surfaces import PASSPHRASE, SECRET_BODY, SECRET_TAG, SECRET_TITLE


def _setup(client, session):
    from tessellate.core import vault

    vault.close()
    vault.create(session, PASSPHRASE)
    session.commit()
    plain = client.post("/entries", json={"content": "plain note alpha", "tags": []}).json()["id"]
    other = client.post("/entries", json={"content": "plain note beta", "tags": []}).json()["id"]
    private = client.post(
        "/entries", json={"content": f"# {SECRET_TITLE}\n\n{SECRET_BODY}", "tags": [SECRET_TAG]}
    ).json()["id"]
    assert client.post(f"/entries/{private}/privacy", json={"private": True}).status_code == 200
    return plain, other, private


def test_a_link_to_a_private_note_is_refused_while_locked(client, session):
    from tessellate.core import vault

    plain, _other, private = _setup(client, session)
    vault.close()
    response = client.post(f"/entries/{plain}/links", json={"target_id": private})
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Unlock first."
    vault.open_with(session, PASSPHRASE)
    assert client.get(f"/entries/{plain}").json()["links"] == []


def test_a_link_from_a_private_note_is_refused_while_locked(client, session):
    from tessellate.core import vault

    plain, _other, private = _setup(client, session)
    vault.close()
    response = client.post(f"/entries/{private}/links", json={"target_id": plain})
    assert response.status_code == 409, response.text


def test_plain_links_still_work_while_locked(client, session):
    from tessellate.core import vault

    plain, other, _private = _setup(client, session)
    vault.close()
    assert client.post(f"/entries/{plain}/links", json={"target_id": other}).status_code == 200


def test_a_private_note_is_not_searchable_open_or_locked(client, session):
    from tessellate.core import vault

    _plain, _other, private = _setup(client, session)
    for phase in ("open", "locked"):
        if phase == "locked":
            vault.close()
        for url in ("/search", "/entries/query"):
            response = client.get(url, params={"q": "combination"})
            ids = [str(h.get("id")) for h in response.json().get("hits", [])]
            assert str(private) not in ids, (phase, url)
            assert "zxqsecrettitle" not in str(response.json().get("hits", [])).lower(), (phase, url)
