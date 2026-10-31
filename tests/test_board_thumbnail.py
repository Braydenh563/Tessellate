"""Raster board thumbnails: stored as files, served with an ETag, current only
while the board has not moved (INBOX 1317)."""

from __future__ import annotations

WEBP = b"RIFF" + (100).to_bytes(4, "little") + b"WEBP" + b"VP8 " + b"\x00" * 90
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _board(client):
    r = client.post("/whiteboard/boards", json={"name": "T", "type": "map", "layout": "tree-right"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _put(client, bid, data, fp="a" * 16):
    return client.put(f"/whiteboard/boards/{bid}/thumbnail?fp={fp}", content=data)


def _state(client, bid):
    return client.get(f"/whiteboard/boards/{bid}/thumbnail/state").json()


def test_put_then_get_round_trips_with_etag_and_304(client):
    bid = _board(client)
    missing = client.get(f"/media/board-thumb/{bid}")
    assert missing.status_code == 404
    assert _put(client, bid, WEBP).status_code == 200
    r = client.get(f"/media/board-thumb/{bid}?v={'a' * 16}")
    assert r.status_code == 200 and r.content == WEBP
    assert r.headers["content-type"] == "image/webp"
    assert "immutable" in r.headers["cache-control"] and "private" in r.headers["cache-control"]
    again = client.get(f"/media/board-thumb/{bid}", headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304


def test_jpeg_accepted_and_replaces_webp(client):
    bid = _board(client)
    _put(client, bid, WEBP)
    assert _put(client, bid, JPEG, fp="b" * 16).status_code == 200
    r = client.get(f"/media/board-thumb/{bid}")
    assert r.headers["content-type"] == "image/jpeg" and r.content == JPEG


def test_size_cap_and_sniff(client):
    bid = _board(client)
    assert _put(client, bid, WEBP + b"\x00" * 70000).status_code == 413
    assert _put(client, bid, b"GIF89a" + b"\x00" * 50).status_code == 415
    assert _put(client, bid, b"<svg></svg>").status_code == 415
    assert _put(client, bid, WEBP, fp="../etc").status_code == 422


def test_unknown_board_404(client):
    assert _put(client, 99999, WEBP).status_code == 404
    missing = client.get("/media/board-thumb/99999")
    assert missing.status_code == 404


def test_thumb_v_current_then_stale_after_edit(client):
    bid = _board(client)
    row = next(b for b in client.get("/whiteboard/boards").json() if b["id"] == bid)
    assert row["thumb_v"] is None
    fp = _state(client, bid)["fp"]
    assert _put(client, bid, WEBP, fp=fp).status_code == 200
    assert _state(client, bid)["stored"] == fp
    row = next(b for b in client.get("/whiteboard/boards").json() if b["id"] == bid)
    assert row["thumb_v"] == fp
    client.post(f"/whiteboard/boards/{bid}/nodes", json={"kind": "topic", "parent_id": None, "text": "x"})
    row = next(b for b in client.get("/whiteboard/boards").json() if b["id"] == bid)
    assert row["thumb_v"] is None
    assert _state(client, bid)["fp"] != fp


def test_purge_removes_file(client):
    from tessellate.core import board_thumbs, deps

    bid = _board(client)
    _put(client, bid, WEBP)
    data_dir = deps.get_config().data_dir
    assert board_thumbs.find(data_dir, bid)
    binned = client.delete(f"/entries/{bid}")
    assert binned.status_code in (200, 204)
    purged = client.delete(f"/entries/{bid}/purge")
    assert purged.status_code in (200, 204)
    assert board_thumbs.find(data_dir, bid) is None


def test_default_board_thumbnail_travels_as_board_zero(client):
    """The default board has no note and no id; the client sends 0 for it
    (the owner, 2026-10-26: it only ever showed the schematic fallback)."""
    row = next(b for b in client.get("/whiteboard/boards").json() if b["id"] is None)
    assert row["thumb_v"] is None
    state = _state(client, 0)
    assert state["stored"] is None
    assert _put(client, 0, WEBP, fp=state["fp"]).status_code == 200
    assert client.get(f"/media/board-thumb/0?v={state['fp']}").content == WEBP
    row = next(b for b in client.get("/whiteboard/boards").json() if b["id"] is None)
    assert row["thumb_v"] == state["fp"]
    assert _put(client, -1, WEBP).status_code == 404


def test_thumb_survives_a_card_note_write_that_leaves_its_title(client):
    """INBOX 1418: the thumbnail was fingerprinted on `max(Entry.updated_at)`
    of the cards' notes, which any write moves (a pin, a body edit, the
    janitor), so the default board's picture went back to the drawn fallback
    without the board changing. Only the title is drawn."""
    note = client.post("/entries", json={"title": "Alpha", "content": "# Alpha\nfirst body"}).json()
    placed = client.post("/whiteboard/nodes", json={"entry_id": note["id"], "board_id": None, "x": 10, "y": 10})
    assert placed.status_code == 200, placed.text
    fp = _state(client, 0)["fp"]
    assert _put(client, 0, WEBP, fp=fp).status_code == 200

    def default_row():
        return next(b for b in client.get("/whiteboard/boards").json() if b["id"] is None)

    assert default_row()["thumb_v"] == fp
    body = client.put(f"/entries/{note['id']}", json={"content": "# Alpha\nsecond body, same title"})
    assert body.status_code == 200, body.text
    pinned = client.put(f"/entries/{note['id']}", json={"pinned": True})
    assert pinned.status_code == 200, pinned.text
    assert default_row()["thumb_v"] == fp
    renamed = client.put(f"/entries/{note['id']}", json={"content": "# Beta\nsecond body"})
    assert renamed.status_code == 200, renamed.text
    assert default_row()["thumb_v"] is None


def test_the_upload_keeps_its_disk_and_database_work_off_the_event_loop():
    """Audit 1028 K18: the async route looked the board up and wrote the file
    on the event loop, and grew the body by `bytes +=`."""
    import inspect

    from tessellate.api import routes_whiteboard

    source = inspect.getsource(routes_whiteboard.put_thumbnail)
    assert "await run_in_threadpool(_thumb_board, db, board_id)" in source
    assert "await run_in_threadpool(board_thumbs.save," in source
    assert "data = bytearray()" in source
