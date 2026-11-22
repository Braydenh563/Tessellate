"""Every reading of a file, in one shape and all of it findable (WORLD_CLASS_PLAN 10, F10).

A file's text could be in five places (three columns on two tables, and
`page_reads`); the search index read three of them for an attachment and two
for an upload, so the vision model's reading of an upload and every page read
in the OCR workspace could not be found by their words. `core/readings.py`
puts the five behind one `readings` view and one indexing rule.
"""

from __future__ import annotations

from types import SimpleNamespace

from tessellate.api import routes_files
from tessellate.core import deps
from tessellate.core.database import Attachment, MediaUpload


def _files(client):
    note = client.post("/entries", json={"content": "A note with a scan"}).json()
    session = deps.get_db().session()
    try:
        att = Attachment(
            entry_id=note["id"],
            filename="receipt.png",
            stored_name="receipt-stored.png",
            caption="A paper receipt",
            ocr_text="Total twelve pounds",
        )
        upload = MediaUpload(
            filename="whiteboard.png",
            original_name="whiteboard.png",
            vision_ocr_text="quarterly heliotrope plan",
            vision_ocr_model="tiny-vision",
        )
        session.add_all([att, upload])
        session.commit()
        return att.id, upload.id
    finally:
        session.close()


def test_the_view_is_one_table_to_sql(client):
    _att_id, upload_id = _files(client)
    session = deps.get_db().session()
    try:
        from sqlalchemy import text

        kinds = {
            row[0]
            for row in session.execute(text("SELECT kind FROM readings WHERE source = 'upload' AND source_id = :i"), {"i": upload_id})
        }
    finally:
        session.close()
    assert kinds == {"vision"}


def test_a_vision_reading_and_a_page_reading_are_findable(client):
    _att_id, upload_id = _files(client)
    hits = client.get("/search?q=heliotrope&hybrid=false").json()["hits"]
    assert any(h.get("source") == "media" and h.get("id") == upload_id for h in hits), hits
    routes_files._remember_page_read(
        ("upload", upload_id),
        SimpleNamespace(page=3, text="the word xylograph is on page three", model="m"),
        "vision",
    )
    hits = client.get("/search?q=xylograph&hybrid=false").json()["hits"]
    assert any(h.get("source") == "media" and h.get("id") == upload_id for h in hits), hits


def test_the_route_returns_every_reading_in_one_shape(client):
    att_id, upload_id = _files(client)
    got = client.get(f"/files/readings?source=upload&id={upload_id}")
    assert got.status_code == 200, got.text
    assert [(r["kind"], r["text"], r["model"]) for r in got.json()] == [("vision", "quarterly heliotrope plan", "tiny-vision")]
    got = client.get(f"/files/readings?source=attachment&id={att_id}").json()
    assert {r["kind"] for r in got} == {"caption", "ocr"}
    assert client.get("/files/readings?source=nope&id=1").status_code == 422
    assert client.get("/files/readings?source=upload&id=99999").status_code == 404
