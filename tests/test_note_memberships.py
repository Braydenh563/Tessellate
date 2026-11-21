"""Note groups (L-world-class-172) and a note's further categories (173).

A group is gathered by hand and no sort moves a note out of it; a note keeps
the one category the filer decides and may also be put in others by a person.
Both are read back on every note (`groups`, `also_in`) and honoured by the
category filters, the Ask context, and the exports.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import zipfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from tessellate.core.database import Base

ROOT = Path(__file__).resolve().parents[1]


def _note(client, text, category=None):
    entry = client.post("/entries", json={"content": text, **({"category": category} if category else {})}).json()
    return entry["id"]


def _get(client, note_id):
    return next(e for e in client.get("/entries").json() if e["id"] == note_id)


# Groups ---------------------------------------------------------------------


def test_a_group_is_made_renamed_and_removed_by_hand(client):
    made = client.post("/groups", json={"name": "  Trip   plans "})
    assert made.status_code == 201 and made.json()["name"] == "Trip plans"
    reply = client.post("/groups", json={"name": "Trip plans"})
    assert reply.status_code == 409
    gid = made.json()["id"]
    reply = client.patch(f"/groups/{gid}", json={"name": "Holiday"})
    assert reply.json()["name"] == "Holiday"
    assert [g["name"] for g in client.get("/groups").json()] == ["Holiday"]
    reply = client.delete(f"/groups/{gid}")
    assert reply.json() == {"deleted": True}
    assert client.get("/groups").json() == []
    reply = client.delete(f"/groups/{gid}")
    assert reply.status_code == 404


def test_notes_join_and_leave_a_group_and_keep_their_category(client):
    a, b = _note(client, "alpha", "Work"), _note(client, "beta", "Home")
    gid = client.post("/groups", json={"name": "Launch"}).json()["id"]
    reply = client.post(f"/groups/{gid}/notes", json={"ids": [a, b, a, 99999]})
    assert reply.json() == {"added": 2}
    reply = client.post(f"/groups/{gid}/notes", json={"ids": [a]})
    assert reply.json() == {"added": 0}
    assert _get(client, a)["groups"] == ["Launch"]
    assert _get(client, a)["category"] == "Work"
    assert client.get("/groups").json()[0]["count"] == 2
    reply = client.post(f"/groups/{gid}/notes/remove", json={"ids": [a]})
    assert reply.json() == {"removed": 1}
    assert _get(client, a)["groups"] == [] and _get(client, b)["groups"] == ["Launch"]


def test_deleting_a_group_keeps_its_notes(client):
    a = _note(client, "keep me")
    gid = client.post("/groups", json={"name": "Temp"}).json()["id"]
    client.post(f"/groups/{gid}/notes", json={"ids": [a]})
    client.delete(f"/groups/{gid}")
    assert _get(client, a)["groups"] == []


def test_a_binned_note_is_not_counted_in_its_group(client):
    a, b = _note(client, "one"), _note(client, "two")
    gid = client.post("/groups", json={"name": "G"}).json()["id"]
    client.post(f"/groups/{gid}/notes", json={"ids": [a, b]})
    client.delete(f"/entries/{b}")
    assert client.get("/groups").json()[0]["count"] == 1


# More than one category -------------------------------------------------------


def test_a_note_can_also_be_in_other_categories(client):
    a = _note(client, "pasta night in Rome", "Recipes")
    out = client.put(f"/entries/{a}/also-in", json={"categories": ["Travel", "Recipes", "Travel", "Family"]})
    assert out.json()["also_in"] == ["Family", "Travel"]  # its own category is not repeated
    note = _get(client, a)
    assert note["category"] == "Recipes" and note["also_in"] == ["Family", "Travel"]
    reply = client.put(f"/entries/{a}/also-in", json={"categories": []})
    assert reply.json()["also_in"] == []
    assert _get(client, a)["also_in"] == []
    reply = client.put("/entries/99999/also-in", json={"categories": ["X"]})
    assert reply.status_code == 404


def test_refiling_into_an_also_category_hides_the_duplicate(client):
    a = _note(client, "x", "Recipes")
    client.put(f"/entries/{a}/also-in", json={"categories": ["Travel"]})
    client.put(f"/entries/{a}", json={"category": "Travel"})
    assert _get(client, a)["also_in"] == []


def test_the_agents_category_filter_finds_a_note_by_either_category(client, session):
    from tessellate.ai.tools._common import _category_clause
    from tessellate.core.database import Entry
    from sqlalchemy import select

    a = _note(client, "pasta night", "Recipes")
    b = _note(client, "museum day", "Travel")
    client.put(f"/entries/{a}/also-in", json={"categories": ["Travel"]})
    found = set(session.scalars(select(Entry.id).where(_category_clause(session, "Travel"))))
    assert {a, b} <= found
    assert a not in set(session.scalars(select(Entry.id).where(_category_clause(session, "Family"))))


def test_the_search_category_filters_see_an_also_category(client, session):
    from tessellate.search import engine

    a = _note(client, "invoice for pasta", "Recipes")
    b = _note(client, "invoice for tickets", "Travel")
    client.put(f"/entries/{a}/also-in", json={"categories": ["Travel"]})

    def hits(q):
        return {h.ref_id for h in engine.search(session, q, ctx=None, hybrid=False) if h.kind == "note"}

    assert hits("cat:Travel invoice") == {a, b}
    assert hits("cat:Recipes invoice") == {a}
    assert hits("invoice -cat:Travel") == set()


def test_the_search_understands_group_names(client, session):
    from tessellate.search import engine

    a, b = _note(client, "invoice for pasta", "Recipes"), _note(client, "invoice for tickets", "Travel")
    gid = client.post("/groups", json={"name": "Trip plan"}).json()["id"]
    client.post(f"/groups/{gid}/notes", json={"ids": [b]})

    def hits(q):
        return {h.ref_id for h in engine.search(session, q, ctx=None, hybrid=False) if h.kind == "note"}

    assert hits('group:"Trip plan" invoice') == {b}
    assert hits("group:trip invoice") == set()
    assert hits('group:"trip PLAN"') == {b}  # no words: the group alone selects
    assert hits("invoice") == {a, b}


def test_merging_a_category_carries_the_also_in_notes_along(client):
    a = _note(client, "x", "Recipes")
    client.put(f"/entries/{a}/also-in", json={"categories": ["Cooking"]})
    cooking = next(c for c in client.get("/categories").json() if c["name"] == "Cooking")
    reply = client.put(f"/categories/{cooking['id']}", json={"name": "Meals"})
    assert reply.status_code == 200
    assert _get(client, a)["also_in"] == ["Meals"]
    meals = next(c for c in client.get("/categories").json() if c["name"] == "Meals")
    client.put(f"/categories/{meals['id']}", json={"name": "Recipes"})  # merge into the primary
    assert _get(client, a)["also_in"] == []


def test_deleting_a_category_drops_it_from_every_note_that_was_also_in_it(client):
    a = _note(client, "x", "Recipes")
    client.put(f"/entries/{a}/also-in", json={"categories": ["Travel"]})
    travel = next(c for c in client.get("/categories").json() if c["name"] == "Travel")
    reply = client.delete(f"/categories/{travel['id']}")
    assert reply.status_code == 200
    assert _get(client, a)["also_in"] == [] and _get(client, a)["category"] == "Recipes"


def test_the_ask_context_names_every_category_a_note_is_in():
    from tessellate.ai.librarian import category_hint

    assert category_hint({"category": "Recipes", "also_in": ["Travel", "Family"]}) == " [Recipes, Travel, Family]"
    assert category_hint({"category": "Recipes"}) == " [Recipes]"
    assert category_hint({"category": "Uncategorised", "also_in": ["Travel"]}) == " [Travel]"
    assert category_hint({"category": "Uncategorised"}) == ""


# Export and import ------------------------------------------------------------


def _shaped(client):
    a = _note(client, "pasta night in Rome", "Recipes")
    client.put(f"/entries/{a}/also-in", json={"categories": ["Travel"]})
    gid = client.post("/groups", json={"name": "Favourites"}).json()["id"]
    client.post(f"/groups/{gid}/notes", json={"ids": [a]})
    return a


def test_the_json_and_csv_exports_carry_both(client):
    a = _shaped(client)
    row = next(e for e in client.get("/export/json").json()["entries"] if e["id"] == a)
    assert row["also_in"] == ["Travel"] and row["groups"] == ["Favourites"]
    rows = list(csv.DictReader(io.StringIO(client.get("/export/csv").text)))
    mine = next(r for r in rows if r["id"] == str(a))
    assert mine["also_in"] == "Travel" and mine["groups"] == "Favourites"


def test_a_markdown_export_comes_back_with_both(client):
    a = _shaped(client)
    archive = zipfile.ZipFile(io.BytesIO(client.get("/export/markdown").content))
    name = next(n for n in archive.namelist() if f"/{a}-" in n)
    text = archive.read(name).decode()
    assert "also-in: [Travel]" in text and "note-groups: [Favourites]" in text
    client.delete(f"/entries/{a}")
    client.post("/import/markdown", files=[("files", ("pasta.md", text.encode(), "text/markdown"))])
    back = next(e for e in client.get("/entries").json() if "pasta night" in e["content"])
    assert back["also_in"] == ["Travel"] and back["groups"] == ["Favourites"]
    assert "also-in" not in back["content"] and "note-groups" not in back["content"]


# Storage ---------------------------------------------------------------------


def test_the_migration_adds_the_three_tables_to_an_existing_notebook(tmp_path):
    db = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    con = sqlite3.connect(db)
    for table in ("entry_categories", "note_group_members", "note_groups"):
        con.execute(f"DROP TABLE {table}")
    con.commit()
    con.close()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.stamp(config, "f7a1c3e5b9d2")
    command.upgrade(config, "a3e7c1d9b5f2")
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"entry_categories", "note_group_members", "note_groups"} <= tables
    command.downgrade(config, "f7a1c3e5b9d2")
    tables = {r[0] for r in sqlite3.connect(db).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not ({"entry_categories", "note_group_members", "note_groups"} & tables)


def test_purging_a_note_leaves_no_membership_rows(client, session):
    from sqlalchemy import func, select

    from tessellate.core.database import EntryCategory, NoteGroupMember

    a = _shaped(client)
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(EntryCategory)) == 1
    assert session.scalar(select(func.count()).select_from(NoteGroupMember)) == 1
    client.delete(f"/entries/{a}")
    reply = client.delete(f"/entries/{a}/purge")
    assert reply.status_code == 200
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(EntryCategory)) == 0
    assert session.scalar(select(func.count()).select_from(NoteGroupMember)) == 0
