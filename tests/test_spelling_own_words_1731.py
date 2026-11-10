"""`GET /spelling/own-words` (INBOX 1731): the words the person's notes use twice.

The spelling second opinion never flags such a word. A private note and every row of a private space contribute nothing, open or shut.
"""

from __future__ import annotations

import pytest

from tessellate.core import vault


@pytest.fixture(autouse=True)
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _words(client) -> list[str]:
    got = client.get("/spelling/own-words")
    assert got.status_code == 200, got.text
    return got.json()["words"]


def test_a_word_used_twice_is_listed_and_a_word_used_once_is_not(client) -> None:
    client.post("/entries", json={"content": "Arvo plans: the doco was great, haha. Uni soon."})
    client.post("/entries", json={"content": "Another arvo, another doco. Sam's lamington."})
    words = _words(client)
    assert "arvo" in words and "doco" in words
    assert "haha" not in words and "lamington" not in words
    assert "sam" not in words


def test_a_possessive_counts_with_its_word(client) -> None:
    client.post("/entries", json={"content": "Priya's bike, then Priya again."})
    assert "priya" in _words(client)


def test_a_private_note_contributes_nothing(client) -> None:
    client.post("/entries", json={"content": "the hushword hushword club"})
    made = client.post("/entries", json={"content": "hushword hushword in a private note"}).json()
    sealed = client.post(f"/entries/{made['id']}/privacy", json={"private": True})
    assert sealed.status_code == 200
    client.post("/entries", json={"content": "hushword once here"})
    words = _words(client)
    # Two uses in the open notes are enough on their own; the private one adds none, so
    # the test below uses a word only the private note repeats.
    only = client.post("/entries", json={"content": "quietword quietword quietword"}).json()
    sealed_only = client.post(f"/entries/{only['id']}/privacy", json={"private": True})
    assert sealed_only.status_code == 200
    assert "quietword" not in _words(client)
    assert "hushword" in words


def test_a_private_space_contributes_nothing_even_when_open(client) -> None:
    from tessellate.core import spacelock

    spacelock.close_all()
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    client.headers.update({"X-Auth-Token": token})
    space = client.post("/spaces", json={"name": "Vault", "is_private": True}).json()["id"]
    client.post("/entries", json={"content": "vaultword vaultword vaultword"}, headers={"X-Workspace-ID": space})
    client.post("/documents", json={"title": "Plan", "content": "boatword boatword"}, headers={"X-Workspace-ID": space})
    client.post("/entries", json={"content": "daylight daylight"})
    client.post("/documents", json={"title": "Plain", "content": "openword openword"})
    unlocked = client.post("/private-spaces/unlock", json={"secret": "first-pass"})
    assert unlocked.status_code == 200
    words = _words(client)
    assert "daylight" in words
    assert "openword" in words
    assert "vaultword" not in words and "boatword" not in words
    seen_in_vault = client.get("/spelling/own-words", headers={"X-Workspace-ID": space}).json()["words"]
    assert "vaultword" not in seen_in_vault
    spacelock.close_all()
