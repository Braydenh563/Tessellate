"""A board's look lives on the board, not in the browser (FEAT-06).

The features audit (2026-10-05): the background colour was one localStorage
key shared by every board and the image a per-board localStorage key, so
neither synced, neither was in a backup, the desktop window and a browser tab
showed different boards, and "clean up orphaned media" deleted the image
(`GET /media/orphans` listed it with `used_by: []`). WHITEBOARD_PLAN decision
24: `background {color, image}` in the board's settings, and media cleanup
reads it.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _upload(client, name="bg.png"):
    return client.post("/media/upload", files={"file": (name, b"\x89PNG\r\n\x1a\n", "image/png")}).json()


def _board(client, name="Background board", kind="board"):
    return client.post("/whiteboard/boards", json={"name": name, "type": kind}).json()


def test_a_background_is_stored_on_the_board_and_read_back(ai_client):
    board = _board(ai_client)
    picture = _upload(ai_client)
    out = ai_client.put(
        f"/whiteboard/boards/{board['id']}",
        json={"background": {"color": "#112233", "image": picture["url"]}},
    )
    assert out.status_code == 200, out.text
    assert out.json()["background"] == {"color": "#112233", "image": picture["url"]}
    state = ai_client.get(f"/whiteboard/?board_id={board['id']}").json()
    assert state["background"] == {"color": "#112233", "image": picture["url"]}
    listed = next(b for b in ai_client.get("/whiteboard/boards").json() if b["id"] == board["id"])
    assert listed["background"]["color"] == "#112233"


def test_a_background_is_a_patch_and_null_removes_one_field(ai_client):
    board = _board(ai_client, kind="map")
    picture = _upload(ai_client)
    ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"color": "#abcdef", "image": picture["url"]}})
    out = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"color": None}}).json()
    assert out["background"] == {"image": picture["url"]}
    #: The settings are a family: type and layout are untouched.
    assert out["type"] == "map"


def test_a_background_image_must_be_this_notebooks_upload(ai_client):
    board = _board(ai_client)
    for bad in ("https://example.com/a.png", "/media/../../etc/passwd", "javascript:alert(1)"):
        out = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"image": bad}})
        assert out.status_code == 422, bad
    out = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"color": "red; x"}})
    assert out.status_code == 422


def test_a_board_background_is_not_an_orphan(ai_client):
    board = _board(ai_client)
    picture = _upload(ai_client)
    ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"image": picture["url"]}})
    listed = ai_client.get("/media/orphans").json()
    assert not any(o["url"] == picture["url"] for o in listed["orphans"])
    media = ai_client.get("/media").json()
    row = next(m for m in media if m["url"] == picture["url"])
    assert row["used_by"] and row["used_by"][0]["kind"] == "board"


def test_the_client_reads_the_board_not_local_storage() -> None:
    source = frontend_text("whiteboard.js")
    assert 'prefs.set("wb-bg-color"' not in source
    assert "prefs.set(wbBgImageKey()" not in source
    assert "wbState.background" in source
    assert "function wbMigrateBackground(" in source


def test_the_sticky_fold_default_is_kept_on_the_board(ai_client):
    """INBOX 792: a board's default for the sticky notes' folded corner is
    stored with its look. Folded is the default, so only `false` is stored."""
    board = _board(ai_client)
    out = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"sticky_fold": False}})
    assert out.status_code == 200, out.text
    assert out.json()["background"] == {"sticky_fold": False}
    state = ai_client.get(f"/whiteboard/?board_id={board['id']}").json()
    assert state["background"] == {"sticky_fold": False}
    on = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"sticky_fold": True}}).json()
    assert on["background"] == {}
    # A patch of one field keeps the others.
    ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"color": "#112233", "sticky_fold": False}})
    kept = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"color": None}}).json()
    assert kept["background"] == {"sticky_fold": False}


def test_the_sticky_fold_is_read_per_note_then_per_board():
    js = frontend_text("whiteboard.js")
    assert "item?.data?.fold ?? wbBoardBackground().sticky_fold !== false" in js
    assert 'el.classed("wb-no-fold", sticky && !wbStickyFolds(d))' in js
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".wb-object-text.wb-sticky.wb-no-fold::after {\n  display: none;" in css
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="wb-sticky-fold"' in html and 'id="wb-fmt-fold"' in html


def test_a_sticky_notes_own_fold_is_stored_with_it(ai_client):
    board = _board(ai_client)
    made = ai_client.post(
        "/whiteboard/objects",
        json={"board_id": board["id"], "kind": "text", "x": 0, "y": 0, "width": 180, "height": 140,
              "data": {"content": "n", "sticky": True, "bg": "#fff4a3", "fold": False}},
    )
    assert made.status_code in (200, 201), made.text
    state = ai_client.get(f"/whiteboard/?board_id={board['id']}").json()
    note = next(o for o in state["objects"] if o["id"] == made.json()["id"])
    assert note["data"]["fold"] is False and note["data"]["sticky"] is True
