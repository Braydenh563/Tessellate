"""GET /audit/export.csv: the activity log as a hand-over file (BACKLOG
section 115, row 11). Who, what, when. Decisions taken with the row: events on
private notes are left out, every cell is defanged against CSV formula
injection, the columns are time, actor, action, entity kind, entity id and
title, and `limit`/`offset`/`X-Total-Count` follow the list endpoints."""

from __future__ import annotations

from tests._help_text import help_chat_text

import csv
import io
from pathlib import Path

import pytest

from tessellate.core import deps, events
from tessellate.core.database import AuditLog

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["time", "actor", "action", "entity kind", "entity id", "title"]


def _rows(response):
    return list(csv.DictReader(io.StringIO(response.text)))


def _add(**fields):
    db = deps.get_db()
    with db.session() as s:
        s.add(AuditLog(**fields))
        s.commit()


def test_export_has_the_six_columns_oldest_first(client):
    client.post("/entries", json={"content": "first note"})
    client.post("/entries", json={"content": "second note", "category": "Ideas"})
    response = client.get("/audit/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = _rows(response)
    assert rows
    assert list(rows[0]) == COLUMNS
    times = [r["time"] for r in rows]
    assert times == sorted(times)
    assert {r["actor"] for r in rows} == {events.ACTOR_USER}
    assert any(r["entity kind"] == "entry" and r["entity id"] for r in rows)


def test_export_never_carries_a_payload_value(client):
    entry = client.post("/entries", json={"content": "the secret sentence"}).json()
    client.put(f"/entries/{entry['id']}", json={"content": "another secret sentence"})
    text = client.get("/audit/export.csv").text
    assert "secret sentence" not in text


@pytest.mark.parametrize("lead", ["=", "+", "-", "@", "\t", "\r"])
def test_every_formula_lead_is_defanged_in_every_cell(client, lead):
    _add(action=lead + "act", entity_type=lead + "kind", actor=lead + "who", detail=lead + 'HYPERLINK("http://x")')
    rows = _rows(client.get("/audit/export.csv"))
    hit = [r for r in rows if "HYPERLINK" in r["title"]]
    assert hit
    for column in ("actor", "action", "entity kind", "title"):
        assert hit[0][column].startswith("'" + lead), (column, hit[0][column])


def test_events_about_private_notes_and_the_vault_are_left_out(client):
    public = client.post("/entries", json={"content": "an ordinary note"}).json()
    from tessellate.core.database import Entry

    with deps.get_db().session() as session:
        row = Entry(content="a private one", is_private=True)
        session.add(row)
        session.commit()
        private_id = row.id
    _add(action="edited", entity_type="entry", entity_id=private_id, detail="PRIVATE-TITLE")
    _add(action="unlocked", entity_type="vault", detail="private notes opened")
    _add(action="edited", entity_type="entry", entity_id=public["id"], detail="PUBLIC-TITLE")
    response = client.get("/audit/export.csv")
    assert "PRIVATE-TITLE" not in response.text
    assert "vault" not in response.text
    assert "PUBLIC-TITLE" in response.text
    shown = [r for r in _rows(response) if r["entity kind"] == "entry" and r["entity id"] == str(private_id)]
    assert shown == []


def test_events_about_a_private_note_stay_out_after_it_is_purged(client):
    """The id filter needs the note to still exist: once a private note is
    purged its id matches nothing, and its events (a title, a clip) were
    exported. A purge now seals them (detail dropped, payload `{"private":
    true}`) and the export leaves sealed events out by that flag."""
    from sqlalchemy import select

    from tessellate.core.database import Entry

    with deps.get_db().session() as session:
        row = Entry(content="a private one", is_private=True, is_deleted=True)
        public = Entry(content="an ordinary one", is_deleted=True)
        session.add_all([row, public])
        session.commit()
        private_id, public_id = row.id, public.id
    _add(action="edited", entity_type="entry", entity_id=private_id, detail="PRIVATE-TITLE", payload={"after": {"content": "PRIVATE-BODY"}})
    _add(action="edited", entity_type="entry", entity_id=public_id, detail="PUBLIC-TITLE")
    assert "PRIVATE-TITLE" not in client.get("/audit/export.csv").text  # by id, while the note exists
    response = client.delete(f"/entries/{private_id}/purge")
    assert response.status_code == 200
    response = client.delete(f"/entries/{public_id}/purge")
    assert response.status_code == 200
    response = client.get("/audit/export.csv")
    assert "PRIVATE-TITLE" not in response.text
    assert [r for r in _rows(response) if r["entity id"] == str(private_id)] == []
    # An ordinary note's events survive its purge; what was sealed lost its body.
    assert "PUBLIC-TITLE" in response.text
    with deps.get_db().session() as session:
        sealed = session.scalars(select(AuditLog).where(AuditLog.entity_id == private_id)).all()
        assert sealed and all(r.detail is None and r.payload == {"private": True} for r in sealed)


def test_an_event_recorded_as_private_is_left_out_by_its_flag(client):
    _add(action="edited", entity_type="entry", entity_id=987654, detail="FLAGGED-TITLE", payload={"private": True})
    _add(action="edited", entity_type="entry", entity_id=987655, detail="UNFLAGGED-TITLE", payload={"after": {"title": "x"}})
    text = client.get("/audit/export.csv").text
    assert "FLAGGED-TITLE" not in text.replace("UNFLAGGED-TITLE", "")
    assert "UNFLAGGED-TITLE" in text


def test_limit_offset_and_the_total_follow_the_list_recipe(client):
    for n in range(5):
        _add(action="created", entity_type="note", detail=f"row {n}")
    everything = client.get("/audit/export.csv")
    total = int(everything.headers["x-total-count"])
    assert total == len(_rows(everything)) >= 5
    page = client.get("/audit/export.csv", params={"limit": 2, "offset": 1})
    assert int(page.headers["x-total-count"]) >= total  # the export itself is logged after the first read
    assert [r["time"] for r in _rows(page)] == [r["time"] for r in _rows(everything)][1:3]
    assert client.get("/audit/export.csv", params={"limit": 0}).status_code == 422
    assert client.get("/audit/export.csv", params={"limit": 100_001}).status_code == 422
    assert client.get("/audit/export.csv", params={"offset": -1}).status_code == 422


def test_entity_filter_and_the_export_is_logged(client):
    client.post("/entries", json={"content": "x"})
    client.get("/audit/export.csv")
    rows = _rows(client.get("/audit/export.csv", params={"entity_type": "data"}))
    assert rows and all(r["entity kind"] == "data" for r in rows)
    assert any(r["title"] == "audit csv" for r in rows)


def test_the_activity_menu_offers_export_activity_and_the_help_says_so():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    button = html.split('id="library-activity-export"', 1)[1].split("</button>", 1)[0]
    assert "Export activity" in button
    help_text = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    help_chat = help_chat_text()
    assert "Export activity" in help_text + help_chat
