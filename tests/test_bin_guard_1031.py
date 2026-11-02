"""One bin guard (audit 1031 BK2, DC8, AR7): a binned note or an archived
document is not rewritten by a PUT.

`GET` on a binned note answered 404 while `PUT` answered 200 and rewrote it,
so the client never learned it was editing something it could not see. Every
content type had its own bin, so the guard was missing on the one that forgot.
`repo/content.py` (once `entry/repo.py`) owns the answer ("This is in the bin. Restore it first.") and
the routes that write to a note or a document ask it."""

from __future__ import annotations

import pytest


def _note(client, text="a note about tram times") -> int:
    r = client.post("/entries", json={"content": text})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_a_binned_note_refuses_a_put_and_keeps_its_words(client):
    nid = _note(client)
    resp = client.delete(f"/entries/{nid}")
    assert resp.status_code == 200
    r = client.put(f"/entries/{nid}", json={"content": "rewritten while binned"})
    assert r.status_code == 409
    assert r.json()["detail"] == "This note is in the bin. Restore it first."
    kept = client.get(f"/entries/{nid}", params={"deleted": "true"}).json()
    assert kept["content"] == "a note about tram times"


def test_a_restored_note_takes_a_put_again(client):
    nid = _note(client)
    client.delete(f"/entries/{nid}")
    resp = client.post(f"/entries/{nid}/restore")
    assert resp.status_code == 200
    resp = client.put(f"/entries/{nid}", json={"content": "back"})
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "path, body",
    [
        ("/entries/{id}/generate-title", None),
        ("/entries/{id}/remove-title", None),
        ("/entries/{id}/wiki-rename", {"old": "a", "new": "b"}),
        ("/entries/{id}/privacy", {"private": True}),
    ],
)
def test_other_writes_to_a_binned_note_are_refused_too(client, path, body):
    nid = _note(client)
    client.delete(f"/entries/{nid}")
    r = client.post(path.format(id=nid), json=body) if body else client.post(path.format(id=nid))
    assert r.status_code == 409, (path, r.status_code, r.text)


def test_a_binned_note_can_still_be_purged_and_restored(client):
    nid = _note(client)
    client.delete(f"/entries/{nid}")
    resp = client.post(f"/entries/{nid}/restore")
    assert resp.status_code == 200
    client.delete(f"/entries/{nid}")
    resp = client.delete(f"/entries/{nid}/purge")
    assert resp.status_code in (200, 204)


def _doc(client) -> int:
    r = client.post("/documents", json={"title": "Plan", "content": "first words"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_an_archived_document_refuses_a_put(client):
    did = _doc(client)
    resp = client.put(f"/documents/{did}/archive")
    assert resp.status_code == 200
    r = client.put(f"/documents/{did}", json={"content": "changed"})
    assert r.status_code == 409
    assert r.json()["detail"] == "This document is archived. Unarchive it first."
    resp = client.get(f"/documents/{did}")
    assert resp.json()["content"] == "first words"


def test_an_archived_document_is_edited_when_the_put_asks_to_unarchive(client):
    did = _doc(client)
    client.put(f"/documents/{did}/archive")
    r = client.put(f"/documents/{did}", json={"content": "changed", "unarchive": True})
    assert r.status_code == 200
    assert r.json()["content"] == "changed"
    assert not r.json().get("archived_at")


def test_an_unknown_file_type_is_refused_naming_the_valid_ones(client):
    did = _doc(client)
    for bad in ("exe", "../../etc", "nonsense"):
        r = client.put(f"/documents/{did}", json={"file_type": bad})
        assert r.status_code == 422, (bad, r.status_code)
        field = r.json()["fields"][0]
        assert field["field"] == "file_type"
        assert "md" in field["message"] and "py" in field["message"]
    resp = client.put(f"/documents/{did}", json={"file_type": "py"})
    assert resp.status_code == 200
    resp = client.put(f"/documents/{did}", json={"file_type": ".PY"})
    assert resp.status_code == 200


def test_the_guard_lives_in_one_module():
    from tessellate.repo import content

    assert callable(content.NOTES.writable) and callable(content.DOCUMENTS.writable)
