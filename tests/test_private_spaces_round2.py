"""Private spaces, round 2 (INBOX 1727): the chat inside, links out, the
browser's reminder words, a restore while locked.

Round 1 (`tests/test_private_spaces.py`) holds the sealing and the lock. This
holds what was left: Atlas reads a private space's notes only in a chat
opened inside it, and that chat keeps nothing in the clear; a link from an
ordinary note to a sealed one shows "A private note" and nothing else, in the
note's connections, its backlinks and the graph; a reminder from a private
space reaches the browser as "A private reminder"; a deleted private space
comes back sealed, and never while locked.
"""

from __future__ import annotations

import sqlite3

import pytest

from tessellate.core import deps, spacelock

PASSWORD = "first-pass"
SECRET = "the locker code is 4715 behind the boathouse"
#: Leak checks look for "boathouse": a timestamp's microseconds can hold "4715" (CI, 2026-11-12).
QUESTION = "where is the locker code kept"
PLACEHOLDER = "A private note"


def _signed_in(client):
    spacelock.close_all()
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"X-Auth-Token": token})
    return client


@pytest.fixture()
def signed_in(client):
    yield _signed_in(client)
    spacelock.close_all()


@pytest.fixture()
def ai_signed_in(ai_client):
    yield _signed_in(ai_client)
    spacelock.close_all()


def _space(client, name="Vault"):
    made = client.post("/spaces", json={"name": name, "is_private": True})
    assert made.status_code == 200, made.text
    return made.json()["id"]


def _unlock(client):
    got = client.post("/private-spaces/unlock", json={"secret": PASSWORD})
    assert got.status_code == 200, got.text


def _lock(client):
    client.post("/private-spaces/lock")


def _in(space_id):
    return {"X-Workspace-ID": space_id}


def _db_text() -> str:
    data_dir = deps.get_config().data_dir
    path = data_dir / "memorymap.db"
    if not path.exists():
        path = next(data_dir.glob("*.db"))
    con = sqlite3.connect(path)
    try:
        out = []
        for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            for row in con.execute(f'SELECT * FROM "{table}"'):
                out.extend(str(cell) for cell in row if cell is not None)
        return "\n".join(out)
    finally:
        con.close()


def _note(client, space_id, content=SECRET):
    made = client.post("/entries", json={"content": content}, headers=_in(space_id))
    assert made.status_code == 201, made.text
    return made.json()["id"]


def _said_to_model(fake) -> str:
    return "\n".join(str(message.get("content", "")) for call in fake.chat_calls for message in call)


# --- 1. Atlas reads a private space only in a chat opened inside it ----------


def test_a_chat_inside_an_open_private_space_reads_its_notes(ai_signed_in, fake_ollama):
    client = ai_signed_in
    space = _space(client)
    _unlock(client)
    note_id = _note(client, space)
    got = client.post("/chat", json={"question": QUESTION}, headers=_in(space))
    assert got.status_code == 200, got.text
    assert note_id in [row["id"] for row in got.json()["raw_results"]]
    assert "4715" in _said_to_model(fake_ollama)


def test_a_chat_anywhere_else_never_reads_them(ai_signed_in, fake_ollama):
    client = ai_signed_in
    space = _space(client)
    _unlock(client)
    note_id = _note(client, space)
    for where in ("default", "all"):
        got = client.post("/chat", json={"question": QUESTION}, headers=_in(where))
        assert got.status_code == 200, got.text
        assert note_id not in [row["id"] for row in got.json()["raw_results"]]
    assert "boathouse" not in _said_to_model(fake_ollama)


def test_a_chat_inside_a_locked_private_space_reads_nothing(ai_signed_in, fake_ollama):
    client = ai_signed_in
    space = _space(client)
    _unlock(client)
    note_id = _note(client, space)
    _lock(client)
    got = client.post("/chat", json={"question": QUESTION}, headers=_in(space))
    assert note_id not in [row["id"] for row in got.json().get("raw_results", [])]
    assert "boathouse" not in _said_to_model(fake_ollama)


def test_the_chat_inside_keeps_nothing_in_the_clear(ai_signed_in, fake_ollama):
    """The turn is a private one (no question log, no audit words), and the
    chat it is saved as, and an Ask box turn, are sealed like a document."""
    client = ai_signed_in
    space = _space(client)
    _unlock(client)
    _note(client, space)
    client.post("/chat", json={"question": QUESTION}, headers=_in(space))
    saved = client.post("/conversations", json={"question": QUESTION, "answer": "It is " + SECRET}, headers=_in(space))
    assert saved.status_code == 201, saved.text
    stored = _db_text()
    assert QUESTION not in stored
    assert SECRET not in stored
    # Still reads back while open, inside the space.
    got = client.get(f"/conversations/{saved.json()['id']}", headers=_in(space))
    assert got.status_code == 200, got.text
    assert SECRET in got.text


def test_a_reminder_made_inside_is_sealed_at_rest(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    made = client.post("/reminders", json={"text": SECRET, "due_at": "2026-12-01T09:00:00"}, headers=_in(space))
    assert made.status_code in (200, 201), made.text
    assert SECRET not in _db_text()
    got = client.get("/reminders", headers=_in(space))
    assert SECRET in got.text


# --- 2. A link out of an ordinary note shows a locked placeholder -------------


def _linked_pair(client):
    """An ordinary note linked to a note that is then moved into a private
    space (the link row stays the ordinary note's)."""
    space = _space(client)
    _unlock(client)
    ordinary = _note(client, "default", "the ordinary side of it")
    secret = _note(client, "default", SECRET)
    linked = client.post(f"/entries/{ordinary}/links", json={"target_id": secret}, headers=_in("default"))
    assert linked.status_code in (200, 201), linked.text
    moved = client.post(f"/spaces/{space}/move-notes", json={"ids": [secret]}, headers=_in("default"))
    assert moved.status_code == 200, moved.text
    _lock(client)
    return ordinary, secret


def test_the_note_view_shows_a_link_to_a_sealed_note_as_a_private_note(signed_in):
    client = signed_in
    ordinary, secret = _linked_pair(client)
    got = client.get(f"/entries/{ordinary}", headers=_in("default"))
    assert got.status_code == 200, got.text
    links = got.json()["links"]
    assert [link["preview"] for link in links if link["entry_id"] == secret] == [PLACEHOLDER]
    assert "boathouse" not in got.text
    connections = client.get(f"/entries/{ordinary}/connections", headers=_in("default"))
    assert connections.status_code == 200, connections.text
    rows = connections.json()["outgoing"] + connections.json()["incoming"]
    assert [row["preview"] for row in rows if row["id"] == secret] == [PLACEHOLDER]
    assert "boathouse" not in connections.text


def test_the_list_shows_it_the_same_way(signed_in):
    client = signed_in
    ordinary, secret = _linked_pair(client)
    listed = client.get("/entries", headers=_in("default")).json()
    row = next(note for note in listed if note["id"] == ordinary)
    assert [link["preview"] for link in row["links"] if link["entry_id"] == secret] == [PLACEHOLDER]


def test_the_graph_draws_a_private_note_with_no_title(signed_in):
    client = signed_in
    ordinary, secret = _linked_pair(client)
    for where in ("default", "all"):
        got = client.get("/graph", headers=_in(where))
        assert got.status_code == 200, got.text
        assert "boathouse" not in got.text
        body = got.json()
        locked = [node for node in body["nodes"] if node.get("type") == "private"]
        assert [node["preview"] for node in locked] == [PLACEHOLDER]
        assert any(edge["source"] == ordinary and edge["target"] == locked[0]["id"] for edge in body["edges"])


def test_backlinks_show_a_sealed_source_as_a_private_note(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    ordinary = _note(client, "default", "Harbour notes")
    secret = _note(client, "default", SECRET + " [[Harbour notes]]")
    moved = client.post(f"/spaces/{space}/move-notes", json={"ids": [secret]}, headers=_in("default"))
    assert moved.status_code == 200, moved.text
    _lock(client)
    got = client.get(f"/entries/{ordinary}/backlinks", headers=_in("default"))
    assert got.status_code == 200, got.text
    assert "boathouse" not in got.text
    assert [(row["kind"], row["title"]) for row in got.json()["links"] if row["id"] == secret] == [("private", PLACEHOLDER)]


def test_open_it_reads_as_itself_again(signed_in):
    client = signed_in
    ordinary, secret = _linked_pair(client)
    _unlock(client)
    got = client.get(f"/entries/{ordinary}", headers=_in("default"))
    assert PLACEHOLDER not in [link["preview"] for link in got.json()["links"]]


# --- 3. The browser's reminder words -----------------------------------------


def test_the_browser_announces_a_private_reminder_without_its_words(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    made = client.post("/reminders", json={"text": SECRET, "due_at": "2026-12-01T09:00:00"}, headers=_in(space))
    assert made.status_code in (200, 201), made.text
    listed = client.get("/reminders", headers=_in("all")).json()
    row = next(item for item in listed if item["id"] == made.json()["id"])
    assert row["notice"] == {"text": "A private reminder", "target_title": None}
    ordinary = client.post("/reminders", json={"text": "water the fern", "due_at": "2026-12-01T09:00:00"}, headers=_in("default"))
    listed = client.get("/reminders", headers=_in("all")).json()
    row = next(item for item in listed if item["id"] == ordinary.json()["id"])
    assert row.get("notice") is None


# --- 4. Delete and restore never unseal --------------------------------------


def test_a_locked_private_space_cannot_be_deleted(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    _note(client, space)
    _lock(client)
    for params in ({}, {"purge": "1"}):
        got = client.delete(f"/spaces/{space}", params=params)
        assert got.status_code == 423, got.text
    assert SECRET not in _db_text()


def test_deleting_keeps_everything_sealed_and_restore_needs_them_open(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    note_id = _note(client, space)
    deleted = client.delete(f"/spaces/{space}")
    assert deleted.status_code == 200, deleted.text
    restore = deleted.json()["restore"]
    assert SECRET not in _db_text()
    # A note the delete moved out, made ordinary meanwhile, goes back in.
    got = client.post(f"/entries/{note_id}/privacy", json={"private": False}, headers=_in("default"))
    assert got.status_code == 200, got.text
    _lock(client)
    got = client.post("/spaces/restore", json=restore)
    assert got.status_code == 423, got.text
    _unlock(client)
    got = client.post("/spaces/restore", json=restore)
    assert got.status_code == 200, got.text
    assert got.json()["is_private"] is True
    assert SECRET not in _db_text()
    note = client.get(f"/entries/{note_id}", headers=_in(space))
    assert note.status_code == 200 and note.json()["is_private"] is True
