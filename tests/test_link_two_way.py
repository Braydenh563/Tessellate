"""A link that runs both ways (INBOX 693, the owner: "what if the user makes
a link meaning for the note link to be omnidirectional and not a
directional link??").

`EntryLink.two_way`: true both ways, false one way, null defers to the
link's type (a type with no inverse has no direction) and, untyped, to one
way. The graph sends the answer as each link edge's `two_way`; the canvas
draws no arrow on it; the link menu's Two-way switch sets it.
"""

from __future__ import annotations

from tests._help_text import help_chat_text

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _save(client, content, **extra):
    response = client.post("/entries", json={"content": content, **extra})
    assert response.status_code == 201
    return response.json()


def _link_edge(client):
    return next(e for e in client.get("/graph").json()["edges"] if e["kind"] == "link")


def test_a_link_is_one_way_until_made_two_way_and_back(client):
    a = _save(client, "first note")
    b = _save(client, "second note")
    link_id = client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]}).json()["links"][0]["link_id"]
    assert _link_edge(client)["two_way"] is False

    response = client.patch(f"/entries/{a['id']}/links/{link_id}", json={"two_way": True})
    assert response.status_code == 200
    assert _link_edge(client)["two_way"] is True

    # From the other end works too: a link belongs to both its notes.
    client.patch(f"/entries/{b['id']}/links/{link_id}", json={"two_way": False})
    assert _link_edge(client)["two_way"] is False


def test_null_defers_to_the_type(client):
    a = _save(client, "a claim")
    b = _save(client, "its evidence")
    link_id = client.post(
        f"/entries/{a['id']}/links", json={"target_id": b["id"], "link_type": "supports"}
    ).json()["links"][0]["link_id"]
    # "Supports" has an inverse ("Supported by"): it has a direction.
    assert _link_edge(client)["two_way"] is False
    client.patch(f"/entries/{a['id']}/links/{link_id}", json={"link_type": "related"})
    # "Related" has none: it reads the same from either end.
    assert _link_edge(client)["two_way"] is True
    # A choice of the link's own wins over its type's.
    client.patch(f"/entries/{a['id']}/links/{link_id}", json={"two_way": False})
    assert _link_edge(client)["two_way"] is False
    client.patch(f"/entries/{a['id']}/links/{link_id}", json={"two_way": None})
    assert _link_edge(client)["two_way"] is True


def test_patching_other_fields_leaves_the_direction_alone(client):
    a = _save(client, "first")
    b = _save(client, "second")
    link_id = client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]}).json()["links"][0]["link_id"]
    client.patch(f"/entries/{a['id']}/links/{link_id}", json={"two_way": True})
    client.patch(f"/entries/{a['id']}/links/{link_id}", json={"props": {"since": "2026"}})
    assert _link_edge(client)["two_way"] is True


def test_the_migration_adds_and_removes_the_column(tmp_path):
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "notebook.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE entry_links (id INTEGER PRIMARY KEY, source_entry_id INTEGER, target_entry_id INTEGER)"
        )
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('d7a3f1c9e2b5')")
        conn.commit()
    finally:
        conn.close()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    def columns():
        conn = sqlite3.connect(str(db_path))
        try:
            return {row[1] for row in conn.execute('PRAGMA table_info("entry_links")')}
        finally:
            conn.close()

    command.upgrade(config, "c8e2a4f6b1d3")
    assert "two_way" in columns()
    command.downgrade(config, "d7a3f1c9e2b5")
    assert "two_way" not in columns()


def test_the_canvas_draws_no_arrow_on_a_two_way_link_and_the_menu_switches_it():
    canvas = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    graph = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
    assert 'else if (arrows && edge.kind === "link" && !edge.two_way) {' in canvas
    assert 'JSON.stringify({ two_way: next })' in graph
    assert 'direction.setAttribute("aria-pressed"' in graph
    help_text = help_chat_text()
    assert "Two-way" in help_text
