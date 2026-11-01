"""One `Content` protocol, one bin guard (audit 1031 row 2a: BK2, DC8, AR7).

A binned note already refused a PUT (`test_bin_guard_1031.py`); the other three
content types each wrote their own bin and each answered differently: a binned
document 404 (it read as gone), a binned board 404, and a file on a binned note
200, renamed and rewritten under a note nobody could see. `repo/content.py`
owns the answer for all four, one sentence per noun, and a read keeps its 404.
"""

from __future__ import annotations

import pytest


def _note(client, text="a note about tram times") -> int:
    r = client.post("/entries", json={"content": text})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _document(client) -> int:
    r = client.post("/documents", json={"title": "Plan", "content": "first words"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _board(client) -> int:
    r = client.post("/whiteboard/boards", json={"name": "Trip plan"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _file(client) -> tuple[int, int]:
    note = _note(client, "host note")
    made = client.post(f"/entries/{note}/files", files={"file": ("handout.md", b"# Handout\n\nwords", "text/markdown")})
    assert made.status_code in (200, 201), made.text
    body = made.json()
    return note, body["id"] if "files" not in body else body["files"][0]["id"]


def test_a_binned_document_refuses_a_put_and_keeps_its_words(client):
    did = _document(client)
    binned = client.delete(f"/documents/{did}")
    assert binned.status_code == 200
    r = client.put(f"/documents/{did}", json={"content": "rewritten while binned"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "This document is in the bin. Restore it first."
    read = client.get(f"/documents/{did}")
    assert read.status_code == 404
    back = client.post(f"/documents/{did}/restore")
    assert back.status_code == 200
    kept = client.get(f"/documents/{did}").json()
    assert kept["content"] == "first words"
    again = client.put(f"/documents/{did}", json={"content": "back"})
    assert again.status_code == 200


@pytest.mark.parametrize(
    "write",
    [
        lambda client, bid: client.put(f"/whiteboard/boards/{bid}", json={"name": "Renamed"}),
        lambda client, bid: client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "hi"}, "board_id": bid}),
    ],
    ids=["rename", "add-object"],
)
def test_a_binned_board_refuses_a_write(client, write):
    bid = _board(client)
    binned = client.delete(f"/entries/{bid}")
    assert binned.status_code == 200
    r = write(client, bid)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "This board is in the bin. Restore it first."
    back = client.post(f"/entries/{bid}/restore")
    assert back.status_code == 200
    again = write(client, bid)
    assert again.status_code in (200, 201)


@pytest.mark.parametrize(
    "write",
    [
        lambda client, fid: client.put(f"/files/{fid}", json={"filename": "renamed.md"}),
        lambda client, fid: client.put(f"/files/{fid}/text", json={"text": "# Rewritten"}),
    ],
    ids=["rename", "save-text"],
)
def test_a_file_on_a_binned_note_refuses_a_write(client, write):
    note, fid = _file(client)
    binned = client.delete(f"/entries/{note}")
    assert binned.status_code == 200
    r = write(client, fid)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "This file is in the bin. Restore it first."
    back = client.post(f"/entries/{note}/restore")
    assert back.status_code == 200
    again = write(client, fid)
    assert again.status_code == 200


def test_an_unknown_id_is_still_404_for_every_kind(client):
    answers = [
        client.put("/documents/987654", json={"content": "x"}),
        client.put("/whiteboard/boards/987654", json={"name": "x"}),
        client.put("/files/987654", json={"filename": "x.md"}),
        client.put("/entries/987654", json={"content": "x"}),
    ]
    assert [r.status_code for r in answers] == [404, 404, 404, 404]


def test_every_kind_is_one_adapter_behind_one_guard():
    from tessellate.repo import content

    assert set(content.KINDS) == {"note", "board", "document", "file"}
    for adapter in content.KINDS.values():
        assert isinstance(adapter, content.Content)
