"""Private spaces (INBOX 1727): membership is the privacy.

What must hold, worst first: nothing in a private space is in the database
in the clear (notes, documents, boards); a locked private space shows
nothing anywhere (lists, search, graph, timeline, export, reminders, AI);
leaving the space asks, and a note private before it came in stays private.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tessellate.core import crypto, deps, spacelock, vault

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "first-pass"
SECRET = "the locker code is 4715 behind the boathouse"


@pytest.fixture()
def signed_in(client):
    spacelock.close_all()
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"X-Auth-Token": token})
    yield client
    spacelock.close_all()


def _space(client, name="Vault", private=True):
    made = client.post("/spaces", json={"name": name, "is_private": private})
    assert made.status_code == 200, made.text
    return made.json()["id"]


def _unlock(client, secret=PASSWORD):
    return client.post("/private-spaces/unlock", json={"secret": secret})


def _in(client, space_id):
    return {"X-Workspace-ID": space_id}


def _db_text() -> str:
    """Every cell of the notebook file, as text, the way `strings` reads it."""
    path = deps.get_config().data_dir / "memorymap.db"
    if not path.exists():
        path = next(deps.get_config().data_dir.glob("*.db"))
    con = sqlite3.connect(path)
    try:
        out = []
        for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            for row in con.execute(f'SELECT * FROM "{table}"'):
                out.extend(str(cell) for cell in row if cell is not None)
        return "\n".join(out)
    finally:
        con.close()


def _fill(client, space_id):
    """A note, a document and a board with a text box and a sketch, all in the space."""
    h = _in(client, space_id)
    note = client.post("/entries", json={"content": SECRET}, headers=h)
    assert note.status_code == 201, note.text
    doc = client.post("/documents", json={"title": "Boathouse plan", "content": SECRET}, headers=h)
    assert doc.status_code == 201, doc.text
    board = client.post("/whiteboard/boards", json={"name": "Boathouse board"}, headers=h)
    assert board.status_code == 201, board.text
    bid = board.json()["id"]
    obj = client.post(
        "/whiteboard/objects",
        json={"board_id": bid, "kind": "text", "x": 0, "y": 0, "width": 100, "height": 60, "data": {"content": SECRET}},
        headers=h,
    )
    assert obj.status_code in (200, 201), obj.text
    sketch = client.post(
        "/whiteboard/sketches", json={"board_id": bid, "data": json.dumps({"d": "M0 0L1 1", "label": SECRET})}, headers=h
    )
    assert sketch.status_code in (200, 201), sketch.text
    return note.json()["id"], doc.json()["id"], bid


def test_the_migration_adds_and_removes_the_four_flags(tmp_path):
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "notebook.db"
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE spaces (id VARCHAR PRIMARY KEY, name VARCHAR)")
    con.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, content TEXT)")
    con.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, content TEXT)")
    con.execute("INSERT INTO entries (content) VALUES ('kept')")
    con.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    con.execute("INSERT INTO alembic_version VALUES ('a9c3e7b1d5f4')")
    con.commit()
    con.close()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    def cols(table):
        c = sqlite3.connect(str(db_path))
        try:
            return {row[1] for row in c.execute(f'PRAGMA table_info("{table}")')}
        finally:
            c.close()

    command.upgrade(config, "d2f6b8a4c1e7")
    assert "is_private" in cols("spaces") and {"is_private", "sealed_by_space"} <= cols("documents")
    assert "sealed_by_space" in cols("entries")
    c = sqlite3.connect(str(db_path))
    assert c.execute("SELECT content, sealed_by_space FROM entries").fetchall() == [("kept", 0)]
    c.close()
    command.downgrade(config, "a9c3e7b1d5f4")
    assert "is_private" not in cols("spaces") and "sealed_by_space" not in cols("entries")


def test_everything_in_a_private_space_is_ciphertext_at_rest(signed_in):
    client = signed_in
    space = _space(client)
    assert _unlock(client).status_code == 200
    _fill(client, space)
    stored = _db_text()
    assert SECRET not in stored
    assert "Boathouse plan" not in stored and "Boathouse board" not in stored
    # And it still reads back while open.
    h = _in(client, space)
    docs = client.get("/documents", headers=h).json()
    listed = docs if isinstance(docs, list) else docs.get("documents", docs.get("items", []))
    assert any(d.get("title") == "Boathouse plan" for d in listed)


def test_a_locked_private_space_shows_nothing_anywhere(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    note_id, doc_id, board_id = _fill(client, space)
    client.post("/reminders", json={"text": SECRET, "due_at": "2026-12-01T09:00:00"}, headers=_in(client, space))
    got = client.post("/private-spaces/lock")
    assert got.json() == {"open": False}

    for h in (_in(client, space), {"X-Workspace-ID": "all"}, {}):
        notes = client.get("/entries", headers=h).json()
        assert all(n["id"] != note_id and n["id"] != board_id for n in notes)
        got = client.get("/documents", headers=h)
        assert SECRET not in json.dumps(got.json())
        for url in ("/search", "/graph", "/timeline", "/reminders", "/whiteboard/boards"):
            got = client.get(url, params={"q": "boathouse"}, headers=h)
            assert got.status_code == 200, url
        got = client.get("/search", params={"q": "boathouse"}, headers=h)
        assert SECRET not in got.text
        got = client.get("/search", params={"q": "boathouse"}, headers=h)
        assert "Boathouse" not in got.text
        got = client.get("/graph", headers=h)
        assert "Boathouse" not in got.text
        got = client.get("/timeline", headers=h)
        assert "Boathouse" not in got.text
        got = client.get("/reminders", headers=h)
        assert SECRET not in got.text
        got = client.get("/whiteboard/boards", headers=h)
        assert "Boathouse" not in got.text
    got = client.get(f"/entries/{note_id}", headers=_in(client, space))
    assert got.status_code == 404
    got = client.get(f"/documents/{doc_id}", headers=_in(client, space))
    assert got.status_code == 404
    got = client.get("/spaces/" + space + "/counts")
    assert got.json() == {"notes": 0, "documents": 0}
    # A write into it is refused, not landed in the clear.
    refused = client.post("/entries", json={"content": "late"}, headers=_in(client, space))
    assert refused.status_code == 423


def test_an_export_skips_a_locked_private_space(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    _fill(client, space)
    client.post("/private-spaces/lock")
    got = client.get("/export/json", headers={"X-Workspace-ID": "all"})
    assert got.status_code == 200
    assert b"Boathouse" not in got.content and SECRET.encode() not in got.content


def test_an_open_private_space_is_exported_only_when_confirmed(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    _fill(client, space)
    plain = client.get("/export/json", headers={"X-Workspace-ID": "all"})
    assert plain.status_code == 200 and SECRET not in plain.text
    asked = client.get("/export/json", params={"include_private_spaces": "1"}, headers={"X-Workspace-ID": "all"})
    assert asked.status_code == 200 and SECRET in asked.text


def _sealed_for(path, workspace, token):
    from starlette.requests import Request

    headers = [(b"x-auth-token", token.encode())] + ([(b"x-workspace-id", workspace.encode())] if workspace else [])
    request = Request({"type": "http", "method": "GET", "path": path, "query_string": b"", "headers": headers})
    session = deps.get_db().session()
    try:
        deps._seal_private_spaces(session, request, workspace)
        return session.info.get("sealed_workspaces")
    finally:
        session.close()


def test_the_ai_reads_a_private_space_only_from_a_chat_opened_inside_it(signed_in):
    client = signed_in
    space = _space(client)
    other = _space(client, "Second vault")
    _unlock(client)
    token = client.headers["X-Auth-Token"]
    with vault.request_scope(token):
        # Open, an ordinary page reads them; the chat elsewhere does not.
        assert _sealed_for("/entries", "default", token) is None
        assert set(_sealed_for("/chat/stream", "default", token)) == {space, other}
        assert set(_sealed_for("/chat/stream", "all", token)) == {space, other}
        assert _sealed_for("/chat/stream", space, token) == [other]
        # An export leaves them out unless asked.
        assert set(_sealed_for("/export/json", "all", token)) == {space, other}
        spacelock.close_all()
        assert set(_sealed_for("/chat/stream", space, token)) == {space, other}


def test_unlocking_takes_the_password_and_the_idle_window_closes_it(signed_in, monkeypatch):
    client = signed_in
    _space(client)
    got = client.get("/private-spaces/status")
    assert got.json()["open"] is False
    assert _unlock(client, "wrong-pass").status_code == 401
    assert _unlock(client).status_code == 200
    got = client.get("/private-spaces/status")
    assert got.json()["open"] is True
    # The app's own polls do not keep them open; the person's input does.
    soon = spacelock._now() + 9 * 60
    monkeypatch.setattr(spacelock, "_now", lambda: soon)
    got = client.post("/private-spaces/touch")
    assert got.json()["open"] is True
    later = soon + 9 * 60
    monkeypatch.setattr(spacelock, "_now", lambda: later)
    got = client.get("/private-spaces/status")
    assert got.json()["open"] is True
    later = soon + 11 * 60
    monkeypatch.setattr(spacelock, "_now", lambda: later)
    got = client.get("/private-spaces/status")
    assert got.json()["open"] is False


def test_the_idle_minutes_follow_the_setting(signed_in):
    client = signed_in
    got = client.put("/preferences", json={"private_space_idle_minutes": 3})
    assert got.status_code == 200
    assert spacelock.idle_minutes() == 3
    got = client.get("/private-spaces/status")
    assert got.json()["idle_minutes"] == 3


def test_the_pin_opens_them_on_this_computer(signed_in, monkeypatch):
    from tessellate.api import routes_private_spaces

    client = signed_in
    _space(client)
    key = vault.key() or vault._dek
    monkeypatch.setattr(routes_private_spaces.routes_auth, "_unlock_with_pin", lambda *a, **k: key if a[3] == "4815" else None)
    assert _unlock(client, "1111").status_code == 401
    assert _unlock(client, "4815").status_code == 200
    got = client.get("/private-spaces/status")
    assert got.json()["open"] is True


def test_a_notes_private_switch_is_locked_on_inside(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    note = client.post("/entries", json={"content": SECRET}, headers=_in(client, space)).json()
    assert note["is_private"] is True
    off = client.post(f"/entries/{note['id']}/privacy", json={"private": False}, headers=_in(client, space))
    assert off.status_code == 409
    assert "Move it out of this space to share it" in off.text


def test_moving_out_keeps_it_private_by_default_or_makes_it_ordinary(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    h = _in(client, space)
    a = client.post("/entries", json={"content": "first " + SECRET}, headers=h).json()["id"]
    b = client.post("/entries", json={"content": "second " + SECRET}, headers=h).json()["id"]
    got = client.post("/spaces/default/move-notes", json={"ids": [a]}, headers=h)
    assert got.status_code == 200
    got = client.post("/spaces/default/move-notes", json={"ids": [b], "keep_private": False}, headers=h)
    assert got.status_code == 200
    home = {"X-Workspace-ID": "default"}
    got = client.get(f"/entries/{a}", headers=home)
    assert got.json()["is_private"] is True
    got = client.get(f"/entries/{b}", headers=home)
    assert got.json()["is_private"] is False


def test_a_note_private_before_it_came_in_stays_private(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    own = client.post("/entries", json={"content": SECRET}).json()["id"]
    client.post(f"/entries/{own}/privacy", json={"private": True})
    client.post(f"/spaces/{space}/move-notes", json={"ids": [own]})
    client.post("/spaces/default/move-notes", json={"ids": [own], "keep_private": False}, headers=_in(client, space))
    got = client.get(f"/entries/{own}", headers={"X-Workspace-ID": "default"})
    assert got.json()["is_private"] is True


def test_moving_a_note_in_seals_it(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    plain = client.post("/entries", json={"content": SECRET}).json()["id"]
    got = client.post(f"/spaces/{space}/move-notes", json={"ids": [plain]})
    assert got.status_code == 200
    assert SECRET not in _db_text()


def test_turning_private_on_seals_everything_and_off_asks(signed_in):
    client = signed_in
    space = _space(client, private=False)
    h = _in(client, space)
    note = client.post("/entries", json={"content": SECRET}, headers=h).json()["id"]
    client.post("/documents", json={"title": "Boathouse plan", "content": SECRET}, headers=h)
    assert SECRET in _db_text()
    on = client.put(f"/spaces/{space}/private", json={"private": True})
    assert on.status_code == 200 and on.json()["changed"] == 2
    assert SECRET not in _db_text() and "Boathouse plan" not in _db_text()
    # Off, keeping them private (the default): still sealed.
    got = client.put(f"/spaces/{space}/private", json={"private": False})
    assert got.status_code == 200
    assert SECRET not in _db_text()
    got = client.get(f"/entries/{note}", headers=h)
    assert got.json()["is_private"] is True


def test_turning_private_off_can_make_them_ordinary(signed_in):
    client = signed_in
    space = _space(client, private=False)
    h = _in(client, space)
    note = client.post("/entries", json={"content": SECRET}, headers=h).json()["id"]
    client.put(f"/spaces/{space}/private", json={"private": True})
    off = client.put(f"/spaces/{space}/private", json={"private": False, "keep_private": False})
    assert off.status_code == 200 and off.json()["changed"] == 1
    got = client.get(f"/entries/{note}", headers=h)
    assert got.json()["is_private"] is False


def test_turning_a_space_ordinary_needs_them_open(signed_in):
    client = signed_in
    space = _space(client)
    got = client.put(f"/spaces/{space}/private", json={"private": False})
    assert got.status_code == 423


def test_a_backup_carries_a_private_space_still_encrypted(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    _fill(client, space)
    made = client.post("/backups")
    assert made.status_code in (200, 201), made.text
    folder = deps.get_config().data_dir / "backups"
    blobs = b"".join(p.read_bytes() for p in folder.rglob("*") if p.is_file())
    assert blobs and SECRET.encode() not in blobs


def test_a_reminder_from_a_private_space_fires_as_a_private_reminder(signed_in):
    from tessellate.core import reminder_notifier

    client = signed_in
    space = _space(client)
    _unlock(client)
    made = client.post("/reminders", json={"text": SECRET, "due_at": "2026-12-01T09:00:00"}, headers=_in(client, space))
    assert made.status_code in (200, 201), made.text
    session = deps.get_db().session()
    try:
        from tessellate.core.database import Reminder

        reminder = session.get(Reminder, made.json()["id"])
        assert reminder_notifier.shown_text(session, reminder) == "A private reminder"
    finally:
        session.close()


def test_closing_the_vault_never_writes_a_sealed_row_in_the_clear(signed_in):
    from tessellate.core.database import Document, SealedWriteRefused

    client = signed_in
    space = _space(client)
    _unlock(client)
    _, doc_id, _ = _fill(client, space)
    session = deps.get_db().session()
    try:
        doc = session.get(Document, doc_id)
        vault.close()
        doc.content = "written while locked"
        with pytest.raises(Exception) as caught:
            session.commit()
        assert isinstance(caught.value, SealedWriteRefused) or "SealedWriteRefused" in repr(caught.value)
    finally:
        session.rollback()
        session.close()
    assert "written while locked" not in _db_text()
    assert crypto.PREFIX in _db_text()


def _add_space_rows(client, space):
    """One bookmark, recording, library picture and note file written inside the space."""
    from tessellate.core.database import Attachment, Bookmark, MediaUpload, Recording

    session = deps.get_db().session()
    try:
        session.info["workspace_id"] = space
        scope = vault.request_scope(client.headers["X-Auth-Token"])
        scope.__enter__()
        entry_id = client.post("/entries", json={"content": "host note"}, headers=_in(client, space)).json()["id"]
        session.add_all(
            [
                Bookmark(url="https://example.com/" + SECRET.replace(" ", "-"), title=SECRET, note=SECRET),
                Recording(title=SECRET, segments=json.dumps([{"start": 0, "end": 1, "text": SECRET}])),
                MediaUpload(filename="p.png", original_name="p.png", ocr_text=SECRET, caption=SECRET, vision_ocr_text=SECRET),
                Attachment(entry_id=entry_id, filename="a.pdf", stored_name="stored-a", ocr_text=SECRET, caption=SECRET),
            ]
        )
        session.commit()
    finally:
        scope.__exit__(None, None, None)
        session.close()


def test_bookmarks_recordings_and_files_made_in_a_private_space_are_sealed(signed_in):
    """L697: what the space owns outright goes in encrypted, and reads back plain while unlocked."""
    from sqlalchemy import select

    from tessellate.core.database import Attachment, Bookmark, MediaUpload, Recording, impersonate_workspace

    client = signed_in
    space = _space(client)
    _unlock(client)
    _add_space_rows(client, space)
    assert "boathouse" not in _db_text()
    session = deps.get_db().session()
    try:
        with vault.request_scope(client.headers["X-Auth-Token"]), impersonate_workspace(session, ""):
            assert session.scalars(select(Bookmark)).first().title == SECRET
            assert session.scalars(select(Recording)).first().title == SECRET
            assert session.scalars(select(MediaUpload)).first().ocr_text == SECRET
            assert session.scalars(select(Attachment)).first().caption == SECRET
    finally:
        session.close()


def test_rows_already_in_a_space_are_sealed_when_it_becomes_private(signed_in):
    client = signed_in
    space = _space(client, private=False)
    _add_space_rows(client, space)
    assert "boathouse" in _db_text()
    _unlock(client)
    made = client.put(f"/spaces/{space}/private", json={"private": True})
    assert made.status_code == 200, made.text
    assert "boathouse" not in _db_text()
