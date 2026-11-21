"""Source text: the route is exercised through the test client; the front-end half has no browser under pytest, so its script is read as text.

AI rename for boards and maps (L348, L280): `POST /whiteboard/boards/{id}/suggest-title`.

Like a document's suggest-title (INBOX 904 B17) it saves nothing: the client
renames through the board's own undoable path. `client` has the AI off, so
these assert the notebook's own fallback and the refusals; the model path is a
fake transport (the standing caveat).
"""

from __future__ import annotations


def _map(client, outline, name="Untitled map"):
    return client.post("/whiteboard/boards/generate", json={"name": name, "outline": outline, "note_ids": []}).json()


def test_a_map_is_named_from_its_topics_and_nothing_is_saved(client):
    board = _map(client, "- Garden plan\n  - Tomatoes in raised beds\n  - Compost heap\n")
    got = client.post(f"/whiteboard/boards/{board['id']}/suggest-title")
    assert got.status_code == 200, got.text
    assert got.json()["by"] == "composer"
    assert got.json()["title"]
    again = [b for b in client.get("/whiteboard/boards").json() if b["id"] == board["id"]][0]
    assert again["title"] == "Untitled map"


def test_an_empty_board_has_nothing_to_name_it_from(client):
    board = client.post("/whiteboard/boards", json={"name": "Blank"}).json()
    got = client.post(f"/whiteboard/boards/{board['id']}/suggest-title")
    assert got.status_code == 422
    assert "nothing" in got.json()["detail"].lower()


def test_a_missing_board_is_a_404(client):
    got = client.post("/whiteboard/boards/999999/suggest-title")
    assert got.status_code == 404


def test_the_board_menu_the_palette_and_the_gallery_all_offer_it():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    assert 'id="wb-suggest-board-name"' in (root / "index.html").read_text(encoding="utf-8")
    assert "wb-suggest-board-name" in (root / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    gallery = (root / "js" / "boards-gallery.js").read_text(encoding="utf-8")
    assert "/suggest-title" in gallery and "Suggest a name" in gallery
