"""L-world-class-22 clause B: moving notes between spaces and the links to notes left behind.

A link is stored in one space and read through that space's filter, so a link
across two spaces is hidden from both. Showing it from either would leak a
space's note (a private one's) into the other, so the move says how many links
it will hide and the screen asks first."""

from __future__ import annotations


def _note(client, text, space=None):
    headers = {"X-Workspace-ID": space} if space else {}
    return client.post("/entries", json={"content": text}, headers=headers).json()


def _links(client, nid, space):
    return client.get(f"/entries/{nid}", headers={"X-Workspace-ID": space}).json().get("links", [])


def _pair(client):
    a = _note(client, "Alpha trip plan")
    b = _note(client, "Beta hotel notes about [[Alpha trip plan]]")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    return a, b


def test_a_link_to_a_note_left_behind_is_hidden_from_both_spaces(client):
    a, b = _pair(client)
    assert [x["entry_id"] for x in _links(client, a["id"], "default")] == [b["id"]]
    client.post("/spaces/work/move-notes", json={"ids": [a["id"]]})
    assert _links(client, a["id"], "work") == []
    assert _links(client, b["id"], "default") == []


def test_the_move_reports_the_links_it_hides_and_where_they_stay(client):
    a, b = _pair(client)
    got = client.post("/spaces/work/move-notes", json={"ids": [a["id"]]}).json()
    assert got["moved"] == 1
    assert got["hidden_links"] == 1
    assert got["staying_in"] == "Default space"


def test_a_preview_counts_without_moving(client):
    a, b = _pair(client)
    got = client.post("/spaces/work/move-notes", json={"ids": [a["id"]], "preview": True}).json()
    assert got["hidden_links"] == 1 and got["moved"] == 0
    assert [x["entry_id"] for x in _links(client, a["id"], "default")] == [b["id"]]


def test_moving_both_ends_hides_nothing(client):
    a, b = _pair(client)
    got = client.post("/spaces/work/move-notes", json={"ids": [a["id"], b["id"]], "preview": True}).json()
    assert got["hidden_links"] == 0
    moved = client.post("/spaces/work/move-notes", json={"ids": [a["id"], b["id"]]}).json()
    assert moved["hidden_links"] == 0
    assert len(_links(client, a["id"], "work")) == 1


def test_a_note_already_in_the_space_is_not_counted(client):
    a, b = _pair(client)
    got = client.post("/spaces/default/move-notes", json={"ids": [a["id"]], "preview": True}).json()
    assert got["hidden_links"] == 0


def test_the_screen_asks_before_hiding_links():
    from tests._app_js import app_js_text

    js = app_js_text()
    assert "keep, true)" in js and "hidden_links" in js
    assert "will be hidden" in js
