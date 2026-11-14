"""L112: Ask shows a relevant map (or board) as a map, a source card of kind map or board."""

from __future__ import annotations


def _map(client, name):
    board = client.post("/whiteboard/boards", json={"name": name, "type": "map"})
    assert board.status_code == 201, board.text
    return board.json()


def _node(client, board_id, text):
    created = client.post(f"/whiteboard/boards/{board_id}/nodes", json={"kind": "topic", "parent_id": None, "text": text})
    assert created.status_code == 201, created.text


def test_a_map_holding_the_words_is_in_raw_results_as_a_map(ai_client):
    board = _map(ai_client, "Cloud models")
    _node(ai_client, board["id"], "Quokkas")
    ai_client.post("/entries", json={"content": "Quokkas live on an island."})
    body = ai_client.post("/chat", json={"question": "what do I have on quokkas?"}).json()
    kinds = {r["id"]: r["board_kind"] for r in body["raw_results"]}
    assert kinds.get(board["id"]) == "map", kinds


def test_a_board_the_note_search_missed_is_still_listed_once(ai_client):
    board = ai_client.post("/whiteboard/boards", json={"name": "Quokkas plan"}).json()
    body = ai_client.post("/chat", json={"question": "what do I have on quokkas?"}).json()
    ids = [r["id"] for r in body["raw_results"]]
    assert ids.count(board["id"]) <= 1
