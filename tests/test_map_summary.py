"""Summarise this branch (the features audit, Phase G; HISTORY's "Open:" list
after FEAT-13's first part).

`POST /whiteboard/boards/{board}/nodes/{node}/summary` writes nothing: it
reads the branch (the topic and everything under it, as an indented outline)
and hands back a few sentences, which the map puts into the topic's own note
for the person to read, change and keep (saved when the note closes, one Undo
step). With a model, the model's sentences from that outline alone; with no
model, or a reply that is not prose, the branch said plainly from its own
topics, which is never wrong and says so (`source: "outline"`). The model is a
fake transport (CLAUDE.md section 4).
"""

from __future__ import annotations

from tests._app_js import frontend_text


def _branch(client):
    board = client.post("/whiteboard/boards", json={"name": "Trip", "type": "map"}).json()
    bid = board["id"]

    def add(text, parent=None):
        body = {"kind": "topic", "text": text}
        if parent is not None:
            body["parent_id"] = parent
        return client.post(f"/whiteboard/boards/{bid}/nodes", json=body).json()["id"]

    root = add("Trip to Lisbon")
    food = add("Food", root)
    add("Pasteis de nata", food)
    add("Sardines", food)
    add("Getting there", root)
    add("Museums", root)
    return bid, root, food


def test_with_no_model_the_branch_is_said_from_its_topics(client):
    bid, root, food = _branch(client)
    before = client.get("/whiteboard/", params={"board_id": bid}).json()["objects"]
    out = client.post(f"/whiteboard/boards/{bid}/nodes/{root}/summary")
    assert out.status_code == 200, out.text
    got = out.json()
    assert got["source"] == "outline" and got["reason"] == "offline"
    assert got["topics"] == 6
    assert got["summary"] == "Trip to Lisbon: Food, Getting there and Museums (6 topics in all)."
    # A summary writes nothing.
    assert client.get("/whiteboard/", params={"board_id": bid}).json()["objects"] == before
    leaf = client.post(f"/whiteboard/boards/{bid}/nodes/{food}/summary").json()
    assert leaf["summary"] == "Food: Pasteis de nata and Sardines (3 topics in all)."


def test_the_model_reads_the_outline_and_its_sentences_come_back(ai_client, fake_ollama):
    bid, root, _ = _branch(ai_client)
    fake_ollama.librarian_reply = "Summary:\nThe trip to Lisbon is planned around food, travel and museums. The food branch names pasteis de nata and sardines."
    got = ai_client.post(f"/whiteboard/boards/{bid}/nodes/{root}/summary").json()
    assert got["source"] == "model"
    assert got["summary"].startswith("The trip to Lisbon is planned")
    assert "Summary:" not in got["summary"]
    # The outline the model read, indented by depth, every topic in it.
    sent = fake_ollama.chat_calls[-1][-1]["content"]
    assert "- Trip to Lisbon" in sent and "    - Pasteis de nata" in sent


def test_a_reply_that_is_not_prose_falls_back_to_the_outline(ai_client, fake_ollama):
    bid, root, _ = _branch(ai_client)
    fake_ollama.librarian_reply = "- Food\n- Museums"
    got = ai_client.post(f"/whiteboard/boards/{bid}/nodes/{root}/summary").json()
    assert got["source"] == "outline" and got["reason"] == "unusable"
    assert got["summary"].startswith("Trip to Lisbon: Food")


def test_a_topic_off_this_map_is_refused(client):
    bid, root, _ = _branch(client)
    refused = client.post(f"/whiteboard/boards/{bid}/nodes/999999/summary")
    assert refused.status_code == 404


def test_the_map_puts_the_summary_into_the_topics_note():
    """The topic menu's row and the palette's run `wbMapSummariseBranch`,
    which opens the topic's note with the summary added (kept on close, one
    Undo step through `wbMapCloseNote`). bm1005-mapmulti.js check 6: the
    note opens inside the window with the summary focused and keeps it, at
    1440 light and 390 dark."""
    from pathlib import Path

    js = Path(__file__).resolve().parents[1] / "frontend" / "js"
    mapjs = frontend_text("whiteboard-map.js")
    body = mapjs[mapjs.index("async function wbMapSummariseBranch(node)") :]
    body = body[: body.index("\n}\n")]
    assert "/summary`, { method: \"POST\" }" in body and "wbMapOpenNote(node.id)" in body
    assert 'row("This topic", "ph:text-align-left Summarise this branch", () => wbMapSummariseBranch(node));' in mapjs
    commands = (js / "whiteboard-commands.js").read_text(encoding="utf-8")
    assert 'id: "summarise-branch"' in commands
