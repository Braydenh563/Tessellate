"""The whole notebook as a markdown folder (WORLD_CLASS_PLAN 25b, Brief 48):
the export of the 500-note fixture, every attachment in it, and every
column of a note either carried by the sidecar or named as left out."""

from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile

import pytest

from tessellate.core import deps
from tessellate.core.database import Entry
from tessellate.entry import export_folder
from tests.fixtures import notebook500

#: Measured on the four-core sandbox under three other agents' load; the cap
#: is generous so a busy machine does not fail it, the print is the number.
EXPORT_CAP_S = 30.0


@pytest.fixture()
def notebook(client):
    session = deps.get_db().session()
    made = notebook500.build(session, deps.get_config().uploads_dir)
    yield session, made
    session.close()


def _export(session) -> tuple[zipfile.ZipFile, export_folder.ExportResult]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        result = export_folder.export(session, deps.get_config().uploads_dir, archive)
    return zipfile.ZipFile(io.BytesIO(buffer.getvalue())), result


def test_every_note_column_is_carried_or_named_as_left_out():
    columns = {column.name for column in Entry.__table__.columns}
    assert set(export_folder.ENTRY_LEFT_OUT) <= columns, "a left-out name that is not a column"
    assert all(reason.strip() for reason in export_folder.ENTRY_LEFT_OUT.values())


def test_the_sidecar_carries_every_column_not_left_out(notebook):
    session, _ = notebook
    snap = export_folder.snapshot(session, deps.get_config().uploads_dir)
    record = next(iter(snap["notes"].values()))
    carried = {c.name for c in Entry.__table__.columns} - set(export_folder.ENTRY_LEFT_OUT)
    assert carried <= set(record), sorted(carried - set(record))


def test_the_500_note_notebook_exports_with_every_attachment(notebook):
    session, made = notebook
    t0 = time.process_time()
    archive, result = _export(session)
    took = time.process_time() - t0
    print(f"\nexport of {made['notes']} notes: {took:.2f} s, zip members {len(archive.namelist())}")
    manifest = json.loads(archive.read("index.json"))
    assert manifest["format"] == export_folder.FORMAT
    assert manifest["counts"]["notes"] == made["notes"]
    assert manifest["counts"]["boards"] == made["boards"]
    assert manifest["counts"]["documents"] == made["documents"]
    assert manifest["counts"]["attachments"] == made["attachments"]
    assert result.missing == [] and manifest["missing"] == []
    for row in manifest["notes"]:
        record = json.loads(archive.read(row["sidecar"]))
        assert len(row["attachments"]) == len(record["attachments"])
        for member, attachment in zip(row["attachments"], record["attachments"]):
            assert hashlib.sha1(archive.read(member)).hexdigest() == attachment["sha1"]  # noqa: S324
    assert took < EXPORT_CAP_S


def test_the_markdown_links_its_attachments_relatively(notebook):
    session, _ = notebook
    archive, _ = _export(session)
    manifest = json.loads(archive.read("index.json"))
    row = next(r for r in manifest["notes"] if len(r["attachments"]) == 2)
    text = archive.read(row["md"]).decode()
    assert text.startswith("---\ncategory: ")
    assert export_folder.ATTACHMENTS_MARK in text
    folder = row["md"].rsplit("/", 1)[0]
    for member in row["attachments"]:
        relative = member[len(folder) + 1:]
        assert f"]({relative})" in text, relative
    assert len(set(row["attachments"])) == 2, "two attachments with one name keep two files"


def test_binned_notes_go_to_the_recycle_bin_folder(notebook):
    session, _ = notebook
    archive, _ = _export(session)
    binned = [n for n in archive.namelist() if n.startswith(f"notes/{export_folder.BIN_FOLDER}/") and n.endswith(".json")]
    assert len(binned) == len([i for i in range(500) if i % 31 == 0])


def test_the_route_streams_the_zip_and_records_the_run(notebook, client):
    reply = client.get("/export/folder")
    assert reply.status_code == 200
    assert reply.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(reply.content))
    assert json.loads(archive.read("index.json"))["counts"]["notes"] == 500
    runs = {run["kind"]: run for run in client.get("/jobs/last-runs").json()["jobs"]}
    assert runs["export"]["status"] == "ok"
    assert "500 notes" in runs["export"]["result"]
