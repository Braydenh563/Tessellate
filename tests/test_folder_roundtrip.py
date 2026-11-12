"""Export then import into an empty notebook, equal on every field
(WORLD_CLASS_PLAN 25b, the gate of Brief 48 step 2).

The comparison is `export_folder.snapshot` before and after: every record
the export writes, with the ids the import made mapped back to the old
ones. `first_difference` names the first field that differs, so a failure
says where rather than "not equal"."""

from __future__ import annotations

import io
import json
import time
import zipfile

import pytest

from tessellate.api.routes_settings_transfer import _parse_frontmatter
from tessellate.core import deps
from tessellate.entry import app_import, export_folder
from tests.fixtures import notebook500


def first_difference(a: object, b: object, path: str = "") -> str | None:
    """The path of the first value that differs, or None when equal."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b), key=str):
            if key not in a or key not in b:
                return f"{path}/{key}: only in {'before' if key in a else 'after'}"
            found = first_difference(a[key], b[key], f"{path}/{key}")
            if found:
                return found
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} items before, {len(b)} after"
        for i, (x, y) in enumerate(zip(a, b)):
            found = first_difference(x, y, f"{path}[{i}]")
            if found:
                return found
        return None
    return None if a == b else f"{path}: {a!r} before, {b!r} after"


def _back(snap: dict, idmap: dict) -> dict:
    """The after-snapshot in the before-snapshot's ids."""
    old = {new: was for was, new in idmap.items()}

    def note(record: dict) -> dict:
        record = dict(record, id=old.get(record["id"], record["id"]))
        record["parent_id"] = old.get(record["parent_id"], record["parent_id"])
        record["links"] = [dict(link, target_entry_id=old.get(link["target_entry_id"])) for link in record["links"]]
        if "canvas" in record:
            canvas = record["canvas"]
            record["canvas"] = dict(canvas, nodes=[dict(n, entry_id=old.get(n["entry_id"])) for n in canvas["nodes"]])
        return record

    documents = {}
    for record in snap["documents"].values():
        documents[record["title"]] = dict(record, id=None, notes=[old.get(n) for n in record["notes"]])
    return {
        "notes": {old[k]: note(v) for k, v in snap["notes"].items() if k in old},
        "boards": {old[k]: note(v) for k, v in snap["boards"].items() if k in old},
        "documents": documents,
    }


def _binned_stamp_aside(snap: dict) -> dict:
    """A binned row's `deleted_at` is the import's own time, not the export's
    (Brief 101b: the bin clock restarts, or the startup sweep purges the row
    just imported), so both sides compare "binned", not the instant."""
    for group in ("notes", "boards"):
        for record in snap[group].values():
            if record.get("deleted_at"):
                record["deleted_at"] = "binned"
    return snap


def _by_title(snap: dict) -> dict:
    return dict(snap, documents={r["title"]: dict(r, id=None) for r in snap["documents"].values()})


def _bin_date_aside(snap: dict) -> dict:
    """A binned note past the bin's days gets a fresh period on import (a
    separate test pins that), so its date is the one field not compared."""
    return dict(snap, notes={k: dict(v, deleted_at=None) if v.get("is_deleted") else v for k, v in snap["notes"].items()})


@pytest.fixture()
def exported(client, tmp_path):
    """The fixture notebook's snapshot and its folder zip, then a fresh,
    empty notebook open in its place."""
    session = deps.get_db().session()
    notebook500.build(session, deps.get_config().uploads_dir)
    before = export_folder.snapshot(session, deps.get_config().uploads_dir)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        export_folder.export(session, deps.get_config().uploads_dir, archive)
    session.close()
    deps.reset_app_state()
    deps.init_app_state(data_dir=tmp_path / "empty")
    yield before, buffer.getvalue()


def _import(data: bytes):
    session = deps.get_db().session()
    result = app_import.read("memorymap", [("tessellate-notebook.zip", data)], parse_frontmatter=_parse_frontmatter)
    written = export_folder.write(session, result, deps.get_config().uploads_dir)
    return session, result, written


def test_the_500_note_notebook_comes_back_equal_on_every_field(exported):
    before, data = exported
    t0 = time.perf_counter()
    session, result, written = _import(data)
    took = time.perf_counter() - t0
    after = export_folder.snapshot(session, deps.get_config().uploads_dir)
    session.close()
    print(f"\nimport of {len(result.notes)} notes and boards: {took:.2f} s; skipped {len(result.skipped)}")
    assert result.skipped == []
    assert written["said"] == []
    assert written["imported"] == 503 and written["already"] == 0
    diff = first_difference(_binned_stamp_aside(_by_title(before)), _binned_stamp_aside(_back(after, written["idmap"])))
    assert diff is None, diff


def test_a_second_import_of_the_same_folder_makes_nothing(exported):
    _, data = exported
    session, _, first = _import(data)
    session.close()
    session, _, second = _import(data)
    session.close()
    assert first["imported"] == 503
    assert (second["imported"], second["already"], second["documents"]) == (0, 503, 0)


def test_the_sidecar_wins_over_the_front_matter(exported):
    _, data = exported
    source = zipfile.ZipFile(io.BytesIO(data))
    manifest = json.loads(source.read("index.json"))
    row = manifest["notes"][1]
    edited = io.BytesIO()
    with zipfile.ZipFile(edited, "w") as archive:
        for name in source.namelist():
            body = source.read(name)
            if name == row["md"]:
                body = body.replace(b"category: ", b"category: Changed by hand ", 1)
            archive.writestr(name, body)
    session, _, written = _import(edited.getvalue())
    sidecar = json.loads(source.read(row["sidecar"]))
    entry_id = written["idmap"][sidecar["id"]]
    after = export_folder.snapshot(session, deps.get_config().uploads_dir)
    session.close()
    assert after["notes"][entry_id]["category"] == sidecar["category"]


def test_a_note_with_no_sidecar_reads_its_front_matter(exported):
    _, data = exported
    source = zipfile.ZipFile(io.BytesIO(data))
    row = json.loads(source.read("index.json"))["notes"][7]
    trimmed = io.BytesIO()
    with zipfile.ZipFile(trimmed, "w") as archive:
        for name in source.namelist():
            if name != row["sidecar"]:
                archive.writestr(name, source.read(name))
    session, result, written = _import(trimmed.getvalue())
    session.close()
    note = next(n for n in result.notes if n.path == row["md"][:-3])
    assert note.record["category"] == "Travel" and note.record["pinned"] is True
    assert export_folder.ATTACHMENTS_MARK not in note.body


def test_the_route_takes_a_memorymap_folder(exported):
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app

    _, data = exported
    client = TestClient(create_app())
    reply = client.post("/import/app?source=memorymap", files=[("files", ("tessellate-notebook.zip", data, "application/zip"))])
    assert reply.status_code == 201, reply.text
    body = reply.json()
    assert body["imported"] == 503 and body["skipped"] == []


def test_a_connector_and_a_map_reference_come_back_joined_to_their_items(client, tmp_path):
    """OPEN row 812: ids inside a board's data were copied, not remapped, so a
    connector came back joined to whatever had its old numbers and a map's
    note node pointed at another note. The export also writes each end by
    place; the import turns it into the new ids."""
    from tessellate.core.database import Entry, WhiteboardNode, WhiteboardObject, WhiteboardSketch
    from tessellate.entry import manager

    session = deps.get_db().session()
    note = manager.create_entry(session, "Joined note")
    board = manager.create_entry(session, "Linked board")
    board.is_board = True
    session.flush()
    card = WhiteboardNode(board_id=board.id, entry_id=note.id, x=0.0, y=0.0)
    box = WhiteboardObject(board_id=board.id, kind="text", data=json.dumps({"content": "Box"}))
    ref = WhiteboardObject(board_id=board.id, kind="note", data=json.dumps({"ref_id": note.id}))
    session.add_all([card, box, ref])
    session.flush()
    session.add(WhiteboardSketch(board_id=board.id, data=json.dumps({
        "type": "link-straight", "sourceId": card.id, "targetId": box.id, "targetKind": "object", "endCap": "arrow"})))
    session.commit()
    note_id, card_id, box_id = note.id, card.id, box.id
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        export_folder.export(session, deps.get_config().uploads_dir, archive)
    session.close()
    deps.reset_app_state()
    deps.init_app_state(data_dir=tmp_path / "empty")
    # The notebook it lands in already has rows, so every new id differs
    # from the old one and a copied id would point at the wrong item.
    session = deps.get_db().session()
    other = manager.create_entry(session, "Already here")
    other.is_board = True
    for i in range(3):
        manager.create_entry(session, f"earlier {i}")
    session.flush()
    session.add_all([WhiteboardNode(board_id=other.id, entry_id=other.id, x=0.0, y=0.0) for _ in range(3)])
    session.add_all([WhiteboardObject(board_id=other.id, kind="text", data="{}") for _ in range(3)])
    session.add_all([WhiteboardSketch(board_id=other.id, data="{}") for _ in range(3)])
    session.commit()
    session.close()
    session, _, written = _import(buffer.getvalue())
    assert written["said"] == [], written["said"]
    new_board = session.query(Entry).filter(Entry.content.like("Linked board%")).one()
    new_note = session.query(Entry).filter(Entry.content.like("Joined note%")).one()
    new_card = session.query(WhiteboardNode).filter_by(board_id=new_board.id).one()
    objects = {o.kind: o for o in session.query(WhiteboardObject).filter_by(board_id=new_board.id)}
    link = json.loads(session.query(WhiteboardSketch).filter_by(board_id=new_board.id).one().data)
    assert (link["sourceId"], link["targetId"]) == (new_card.id, objects["text"].id), link
    assert link["targetKind"] == "object" and link["endCap"] == "arrow"
    assert json.loads(objects["note"].data)["ref_id"] == new_note.id
    assert new_note.id != note_id and new_card.id != card_id and objects["text"].id != box_id
    session.close()


def test_a_note_binned_long_ago_comes_in_with_a_fresh_bin_period(exported):
    """It used to keep its old date, so the next start purged what the import
    had just made. A note still inside the bin's days keeps its own date."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from tessellate.core.database import Entry

    before, data = exported
    session, _, written = _import(data)
    try:
        binned = list(session.scalars(select(Entry).where(Entry.is_deleted.is_(True))))
        assert len(binned) == len([r for r in before["notes"].values() if r["is_deleted"]]) > 0
        floor = datetime.now(timezone.utc) - timedelta(minutes=5)
        for entry in binned:
            stamp = entry.deleted_at if entry.deleted_at.tzinfo else entry.deleted_at.replace(tzinfo=timezone.utc)
            assert stamp > floor, (entry.id, entry.deleted_at)
        from tessellate.entry import manager_purge

        assert manager_purge.purge_expired_deleted(session, 30) == 0  # the start-up purge keeps them
    finally:
        session.close()


def test_an_import_commits_in_batches_not_per_note(exported, monkeypatch):
    """One commit per note was most of a 5,000-note import's time (45.9 s)."""
    from sqlalchemy.orm import Session

    _, data = exported
    commits = []
    real = Session.commit
    monkeypatch.setattr(Session, "commit", lambda self: (commits.append(1), real(self))[1])
    session, _, written = _import(data)
    session.close()
    assert written["imported"] == 503
    assert len(commits) < 60, f"{len(commits)} commits for 503 notes"
