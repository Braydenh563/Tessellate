"""Brief 98: goals and lists, the /goals API (create, tick, progress, delete with Undo's shape, limits)."""

from __future__ import annotations

import sqlite3

import pytest

from tessellate.core.database_manager import DatabaseManager


def _make(client, title="Run a half marathon", kind="goal", **extra):
    response = client.post("/goals", json={"title": title, "kind": kind, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_a_goal_starts_with_no_progress(client):
    made = _make(client, target_date="2027-06-01")
    assert made["kind"] == "goal" and made["target_date"] == "2027-06-01"
    assert made["progress"] == {"total": 0, "done": 0, "percent": 0}


def test_ticking_items_moves_the_progress(client):
    goal = _make(client, items=[{"text": "Buy shoes"}, {"text": "Run 5 km"}, {"text": "Run 10 km"}, {"text": "Run 21 km"}])
    first = goal["items"][0]["id"]
    body = client.patch(f"/goals/{goal['id']}/items/{first}", json={"done": True}).json()
    assert body["progress"] == {"total": 4, "done": 1, "percent": 25}
    body = client.patch(f"/goals/{goal['id']}/items/{first}", json={"done": False}).json()
    assert body["progress"]["done"] == 0


def test_an_item_is_added_renamed_and_removed(client):
    goal = _make(client, "Packing", "list")
    added = client.post(f"/goals/{goal['id']}/items", json={"text": "passport"}).json()
    item = added["items"][0]["id"]
    renamed = client.patch(f"/goals/{goal['id']}/items/{item}", json={"text": "  passport  and visa "}).json()
    assert renamed["items"][0]["text"] == "passport and visa"
    sent = client.delete(f"/goals/{goal['id']}/items/{item}").json()["text"]
    assert sent == "passport and visa"
    assert client.get("/goals").json()["goals"][0]["items"] == []


def test_the_list_filters_by_kind_and_state_and_counts_open_ones(client):
    goal = _make(client)
    _make(client, "Shopping", "list")
    finished = client.patch(f"/goals/{goal['id']}", json={"done": True}).json()
    assert finished["done_at"]
    assert [g["title"] for g in client.get("/goals").json()["goals"]] == ["Shopping"]
    assert [g["title"] for g in client.get("/goals?state=done").json()["goals"]] == ["Run a half marathon"]
    assert len(client.get("/goals?state=all").json()["goals"]) == 2
    body = client.get("/goals?kind=list&state=all").json()
    assert [g["kind"] for g in body["goals"]] == ["list"]
    assert body["counts"] == {"goal": 0, "list": 1}
    reopened = client.patch(f"/goals/{goal['id']}", json={"done": False}).json()
    assert reopened["done_at"] is None


def test_a_delete_answers_the_whole_goal_so_undo_can_create_it_again(client):
    goal = _make(client, items=[{"text": "a", "done": True}, {"text": "b"}])
    gone = client.delete(f"/goals/{goal['id']}").json()
    assert gone["progress"]["done"] == 1 and len(gone["items"]) == 2
    assert client.get("/goals").json()["goals"] == []
    back = client.post("/goals", json={k: gone[k] for k in ("title", "kind", "target_date", "items")}).json()
    assert back["progress"] == {"total": 2, "done": 1, "percent": 50}


@pytest.mark.parametrize(
    "body",
    [{"title": "   "}, {"title": "x", "target_date": "next week"}, {"title": "x", "target_date": "2027-13-40"}, {"title": "x", "kind": "plan"}, {"title": "x", "items": [{"text": " "}]}],
)
def test_what_cannot_be_stored_is_refused(client, body):
    sent = client.post("/goals", json=body).status_code
    assert sent == 422
    assert client.get("/goals?state=all").json()["goals"] == []


def test_an_unknown_goal_or_item_is_a_404(client):
    goal = _make(client)
    sent = client.patch("/goals/999", json={"title": "x"}).status_code
    assert sent == 404
    sent = client.delete("/goals/999").status_code
    assert sent == 404
    sent = client.post("/goals/999/items", json={"text": "x"}).status_code
    assert sent == 404
    sent = client.patch(f"/goals/{goal['id']}/items/999", json={"done": True}).status_code
    assert sent == 404


def test_an_item_of_another_goal_is_not_reachable_through_this_one(client):
    one, two = _make(client, "One", items=[{"text": "a"}]), _make(client, "Two")
    sent = client.patch(f"/goals/{two['id']}/items/{one['items'][0]['id']}", json={"done": True}).status_code
    assert sent == 404


def test_the_items_of_one_goal_are_capped(client, monkeypatch):
    from tessellate.repo import goals

    monkeypatch.setattr(goals, "MAX_ITEMS", 2)
    goal = _make(client)
    for word in ("a", "b"):
        sent = client.post(f"/goals/{goal['id']}/items", json={"text": word}).status_code
        assert sent == 201
    sent = client.post(f"/goals/{goal['id']}/items", json={"text": "c"}).status_code
    assert sent == 422


def test_an_older_notebook_gains_the_tables_on_its_next_start(tmp_path):
    """The migration: a database made before goals existed has no table; the start builds both, with their index."""
    path = tmp_path / "old.db"
    DatabaseManager(path).engine.dispose()
    conn = sqlite3.connect(str(path))
    conn.executescript("DROP TABLE goal_items; DROP TABLE goals; PRAGMA user_version = 0;")
    conn.commit()
    conn.close()
    DatabaseManager(path).engine.dispose()
    conn = sqlite3.connect(str(path))
    try:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    finally:
        conn.close()
    assert {"goals", "goal_items"} <= names
