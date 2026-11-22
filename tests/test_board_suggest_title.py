"""AI rename for boards and maps (L348, L280): `POST /whiteboard/boards/{id}/suggest-title`.

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


def test_a_private_cards_title_never_names_the_board(client, session):
    """Review 5899364438 item 4: a pinned private note's title stayed in the words a name is cut from."""
    from tessellate.api import wb_boards
    from tessellate.core import vault

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    board = client.post("/whiteboard/boards", json={"name": "Blank"}).json()
    plain = client.post("/entries", json={"content": "# Garden plan\nBeds."}).json()["id"]
    secret = client.post("/entries", json={"content": "# Surprise party\nShh."}).json()["id"]
    made_private = client.post(f"/entries/{secret}/privacy", json={"private": True})
    assert made_private.status_code == 200
    for eid in (plain, secret):
        client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": board["id"], "x": 0, "y": 0})
    words = wb_boards._board_words(session, board["id"])
    vault.close()
    assert "Garden plan" in words and "Surprise" not in words


def test_a_slow_model_falls_back_to_the_boards_words(client, monkeypatch):
    """Item 4: the model runs on a job thread with a timeout, so a stalled model gives the composer's name."""
    import time

    from tessellate.ai import librarian
    from tessellate.api import wb_boards
    from tessellate.core import deps

    board = _map(client, "- Garden plan\n  - Tomatoes in raised beds\n")
    monkeypatch.setattr(wb_boards, "_TITLE_SECONDS", 0.05)
    monkeypatch.setattr(type(deps.get_ollama()), "is_running", lambda self: True)
    monkeypatch.setattr(librarian, "generate_title", lambda *a: time.sleep(1) or "Too late")
    got = client.post(f"/whiteboard/boards/{board['id']}/suggest-title")
    assert got.status_code == 200 and got.json()["by"] == "composer"
