"""Source text: the route is exercised through the test client; the front-end half has no browser under pytest, so its script is read as text.

The affinity sort (the features audit, Phase G; WHITEBOARD_PLAN decision 36's
sibling): a board's stickies grouped into named themes, each shown with the
notes in the notebook that back it. `POST /whiteboard/boards/{board}/affinity`
writes nothing; the board draws the accepted groups as frames in one Undo
step. With a model the model names the groups (a fake transport here); with no
model, or a reply that is not lines of `Name: numbers`, stickies that share a
word are grouped by it, which is never wrong and says so (`source: "words"`).
"""

from __future__ import annotations

from pathlib import Path

TEXTS = [
    "Tomato pruning schedule",
    "Tomato feed weekly",
    "Compost heap turning",
    "Compost bin lid",
    "Book the flights",
    "Tax return deadline",
]


def _board(client, texts=TEXTS):
    bid = client.post("/whiteboard/boards", json={"name": "Sort me", "type": "board"}).json()["id"]
    ids = []
    for i, text in enumerate(texts):
        made = client.post(
            "/whiteboard/objects",
            json={"kind": "text", "board_id": bid, "x": i * 40, "y": 0, "z": i, "width": 160, "height": 100,
                  "data": {"content": text, "sticky": True}},
        )
        assert made.status_code in (200, 201), made.text
        ids.append(made.json()["id"])
    return bid, ids


def _names(got):
    return {g["name"]: [i["text"] for i in g["items"]] for g in got["groups"]}


def test_with_no_model_stickies_that_share_a_word_are_grouped_by_it(client):
    bid, ids = _board(client)
    before = client.get("/whiteboard/", params={"board_id": bid}).json()["objects"]
    out = client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": ids})
    assert out.status_code == 200, out.text
    got = out.json()
    assert got["source"] == "words" and got["reason"] == "offline"
    assert _names(got) == {
        "Compost": ["Compost heap turning", "Compost bin lid"],
        "Tomato": ["Tomato pruning schedule", "Tomato feed weekly"],
        "Other": ["Book the flights", "Tax return deadline"],
    }
    assert sum(len(g["ids"]) for g in got["groups"]) == len(ids)
    # Writes nothing.
    after = client.get("/whiteboard/", params={"board_id": bid}).json()["objects"]
    assert after == before


def test_each_sticky_carries_the_notes_that_back_it(client):
    note = client.post("/entries", json={"content": "# Tomato pruning\n\npinch the side shoots every week"}).json()
    bid, ids = _board(client)
    got = client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": ids}).json()
    tomato = next(g for g in got["groups"] if g["name"] == "Tomato")
    backed = {i["text"]: i["notes"] for i in tomato["items"]}
    assert backed["Tomato pruning schedule"] and backed["Tomato pruning schedule"][0] == {"id": note["id"], "title": "Tomato pruning"}
    # The search pads thin results with near misses; a note that shares no word with the sticky is not evidence for it.
    client.post("/entries", json={"content": "# Compost heap\n\nturn it weekly"})
    padded = client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": ids}).json()
    book = next(i for g in padded["groups"] for i in g["items"] if i["text"] == "Book the flights")
    assert book["notes"] == []
    other = next(g for g in got["groups"] if g["name"] == "Other")
    assert all(not i["notes"] for i in other["items"])


def test_the_model_names_the_groups_and_a_bad_number_is_dropped(ai_client, fake_ollama):
    bid, ids = _board(ai_client)
    fake_ollama.librarian_reply = (
        "Here are the groups:\nGarden care: 1, 2, 3, 4, 99\nAdmin: 5, 6\nGarden care again: 1"
    )
    got = ai_client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": ids}).json()
    assert got["source"] == "model"
    assert _names(got) == {
        "Garden care": TEXTS[:4],
        "Admin": TEXTS[4:],
    }
    sent = fake_ollama.chat_calls[-1][-1]["content"]
    assert "[1] Tomato pruning schedule" in sent and "[6] Tax return deadline" in sent


def test_a_sticky_the_model_left_out_is_placed_by_words_not_lost(ai_client, fake_ollama):
    bid, ids = _board(ai_client)
    fake_ollama.librarian_reply = "Tomatoes: 1, 2\nAdmin: 5, 6"
    got = ai_client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": ids}).json()
    assert sorted(i for g in got["groups"] for i in g["ids"]) == sorted(ids)
    assert _names(got)["Tomatoes"] == TEXTS[:2]
    assert any("Compost heap turning" in v for v in _names(got).values())


def test_a_reply_that_is_not_groups_falls_back_to_words(ai_client, fake_ollama):
    bid, ids = _board(ai_client)
    fake_ollama.librarian_reply = "Tomatoes and compost are the main themes."
    got = ai_client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": ids}).json()
    assert got["source"] == "words" and got["reason"] == "unusable"
    assert "Tomato" in _names(got)


def test_too_few_stickies_and_foreign_ids_are_refused(client):
    bid, ids = _board(client)
    other, other_ids = _board(client, ["Elsewhere one", "Elsewhere two"])
    single = client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": ids[:1]})
    assert single.status_code == 422
    foreign = client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": other_ids})
    assert foreign.status_code == 422


def test_the_board_draws_one_frame_per_accepted_group_in_one_undo_step():
    """`wbMapLazy.affinitySort` (Edit menu, palette "affinity-sort") posts the
    selected stickies, previews the groups per frame with the notes behind each
    sticky, and for the ticked ones moves the stickies and makes the frames
    inside one `wbRecordGesture`. affinity1112.js measures it live."""
    js = Path(__file__).resolve().parents[1] / "frontend" / "js"
    more = (js / "whiteboard-map-more.js").read_text(encoding="utf-8")
    body = more[more.index("async function wbAffinityRun()") :]
    body = body[: body.index("\n  }\n")]
    assert "/affinity`" in body and "wbRecordGesture(" in body
    assert "affinitySort: wbAffinityRun" in more
    commands = (js / "whiteboard-commands.js").read_text(encoding="utf-8")
    assert 'id: "affinity-sort"' in commands


def test_a_slow_model_times_out_and_the_words_rule_sorts(ai_client, fake_ollama, monkeypatch):
    import time

    from tessellate.api import routes_board_affinity

    bid, ids = _board(ai_client)
    real = fake_ollama.chat
    monkeypatch.setattr(fake_ollama, "chat", lambda *a, **k: (time.sleep(1.0), real(*a, **k))[1])
    monkeypatch.setattr(routes_board_affinity, "MODEL_SECONDS", 0.1)
    started = time.perf_counter()
    got = ai_client.post(f"/whiteboard/boards/{bid}/affinity", json={"ids": ids}).json()
    assert time.perf_counter() - started < 0.9
    assert got["source"] == "words" and got["reason"] == "failed"
    assert "Compost" in _names(got)
