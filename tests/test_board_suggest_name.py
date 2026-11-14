"""L280: a board or map can be named from what is on it, as a document can
(INBOX 904 B17). The model writes the name when one runs, else the board's own
words (`composer_voice.title_for`) are cut to one. Nothing is saved by the
route; the client renames through Rename's undoable path."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS = "Packed the tent and the stove for the coast trip on Friday"


def _board(client, kind="board"):
    return client.post("/whiteboard/boards", json={"name": "Untitled board", "type": kind}).json()


def _text(client, bid, content, kind="text", **extra):
    body = {"kind": kind, "data": {"content": content}, "board_id": bid, "x": 0, "y": 0, "z": 1, "width": 200, "height": 80, **extra}
    out = client.post("/whiteboard/objects", json=body)
    assert out.status_code in (200, 201), out.text
    return out.json()


def test_with_no_model_the_name_is_the_boards_own_words_and_nothing_is_saved(client):
    bid = _board(client)["id"]
    _text(client, bid, WORDS)
    out = client.post(f"/whiteboard/boards/{bid}/suggest-title")
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["by"] == "composer"
    assert body["title"] and all(w.lower().strip(",.") in WORDS.lower() for w in body["title"].split()), body
    titles = [b["title"] for b in client.get("/whiteboard/boards").json() if b["id"] == bid]
    assert titles == ["Untitled board"]


def test_a_map_is_named_from_its_centre_topic_first(client):
    bid = _board(client, "map")["id"]
    _text(client, bid, "Garden plans for spring", kind="topic")
    out = client.post(f"/whiteboard/boards/{bid}/suggest-title").json()
    assert out["title"].lower().startswith("garden plans"), out


def test_a_running_model_writes_the_name(ai_client, fake_ollama):
    bid = _board(ai_client)["id"]
    _text(ai_client, bid, WORDS)
    fake_ollama.librarian_reply = "Coast trip packing"
    body = ai_client.post(f"/whiteboard/boards/{bid}/suggest-title").json()
    assert body == {"title": "Coast trip packing", "by": "model"}


def test_an_empty_board_has_nothing_to_name_it_from(client):
    bid = _board(client)["id"]
    out = client.post(f"/whiteboard/boards/{bid}/suggest-title")
    assert out.status_code == 422 and "nothing" in out.json()["detail"].lower()


def test_the_gallery_menu_offers_it_and_renames_with_undo():
    js = (ROOT / "frontend" / "js" / "boards-gallery.js").read_text(encoding="utf-8")
    # One item (two branches each added one), renamed through the helper Rename uses, which pushes the Undo.
    assert js.count('"ph:sparkle Suggest a name"') == 1
    item = js[js.index('"ph:sparkle Suggest a name"'):][:600]
    helper = js[js.index("const renameBoardWithUndo"):][:600]
    assert "/suggest-title" in item and "renameBoardWithUndo(" in item and "pushUndo(" in helper
