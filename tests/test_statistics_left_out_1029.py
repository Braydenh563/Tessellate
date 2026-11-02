"""Statistics says what it leaves out; About health counts the whole database
(audit 1029 X13, X17, rank 51)."""

from __future__ import annotations

from tessellate.api import routes_debug
from tessellate.core.database import Entry
from tessellate.entry import manager

from tests._app_js import app_js_text


def _notes(client, session):
    ids = {}
    for key, text in (("normal", "a normal note"), ("archived", "an archived note"), ("private", "a private note")):
        ids[key] = client.post("/entries", json={"content": text}).json()["id"]
    client.post(f"/entries/{ids['archived']}/archive")
    session.get(Entry, ids["private"]).is_private = True
    session.commit()


def test_the_page_names_the_notes_whose_words_and_growth_it_does_not_read(client, session):
    _notes(client, session)
    book = client.get("/statistics").json()["notebook"]
    assert book["notes"] == manager.count_notes(session) == 3
    # Only the plain note's three words are read; the other two are left out, and said so.
    assert book["words"] == 3
    assert book["left_out"] == {"private": 1, "archived": 1}


def test_nothing_is_left_out_of_an_ordinary_notebook(client):
    client.post("/entries", json={"content": "one plain note"})
    assert client.get("/statistics").json()["notebook"]["left_out"] == {"private": 0, "archived": 0}


def test_the_page_draws_the_left_out_line_only_when_there_is_one():
    js = app_js_text()
    start = js.index("function statsNotebookSection")
    body = js[start : js.index("function statsRemindersSection")]
    assert "statsLeftOutLine(book.left_out)" in body and "leave out" in js


def test_db_footprint_is_the_main_file_plus_its_wal_and_shm(tmp_path):
    db = tmp_path / "x.db"
    db.write_bytes(b"m" * 4096)
    (tmp_path / "x.db-wal").write_bytes(b"w" * 3000)
    (tmp_path / "x.db-shm").write_bytes(b"s" * 500)
    assert routes_debug.db_footprint(db) == {"main_bytes": 4096, "wal_bytes": 3500, "size_bytes": 7596}
    assert routes_debug.db_footprint(tmp_path / "missing.db")["size_bytes"] == 0


def test_health_reports_the_footprint_it_sums(client):
    client.post("/entries", json={"content": "make the file"})
    db = client.get("/debug/health").json()["db"]
    assert db["size_bytes"] == db["main_bytes"] + db["wal_bytes"] > 0
