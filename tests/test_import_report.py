"""The import report as a page (WORLD_CLASS_PLAN 25b, Brief 48 steps 3 and
4): counts, every skipped item named with its reason, reachable from the
Activity panel's finished line; and the import
as a job with progress per hundred notes and a Stop that lands within 2 s
and keeps what was written."""

from __future__ import annotations

import io
import json
import threading
import time
import zipfile

import pytest

from tessellate.api.routes_settings import _parse_frontmatter
from tessellate.core import activity, deps
from tessellate.core.database import Entry
from tessellate.entry import app_import, export_folder
from tests.fixtures import notebook500

BAD = {
    "notes/Garden/9001-broken.json": b"{not json",
    "notes/Garden/9002-empty.md": b"---\ncategory: Garden\n---\n",
    "notes/Garden/9003-binary.md": b"\xff\xfe\xfa not text",
    "stray.exe": b"MZ",
}


@pytest.fixture()
def folder_with_bad_files(client, tmp_path):
    """A 20-note folder export with five deliberate faults: four bad files
    and one attachment taken out."""
    session = deps.get_db().session()
    notebook500.build(session, deps.get_config().uploads_dir, count=20)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        export_folder.export(session, deps.get_config().uploads_dir, archive)
    session.close()
    source = zipfile.ZipFile(io.BytesIO(buffer.getvalue()))
    manifest = json.loads(source.read("index.json"))
    dropped = next(row["attachments"][0] for row in manifest["notes"] if row["attachments"])
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name in source.namelist():
            if name != dropped:
                archive.writestr(name, source.read(name))
        for name, data in BAD.items():
            archive.writestr(name, data)
    #: Into an empty notebook, so every note is new.
    deps.reset_app_state()
    deps.init_app_state(data_dir=tmp_path / "empty")
    return out.getvalue(), dropped


def test_the_report_names_every_skip_with_its_reason(client, folder_with_bad_files):
    data, dropped = folder_with_bad_files
    reply = client.post("/import/app?source=memorymap", files=[("files", ("notebook.zip", data, "application/zip"))])
    assert reply.status_code == 201, reply.text
    body = reply.json()
    report = client.get(f"/import/reports/{body['report']}").json()
    names = {item["name"]: item["reason"] for item in report["skipped"]}
    assert names == {
        "notes/Garden/9001-broken.json": "the sidecar could not be read",
        "notes/Garden/9002-empty.md": "empty",
        "notes/Garden/9003-binary.md": "not a text file",
        "stray.exe": "not part of a Tessellate folder export",
        dropped: "attachment missing from the folder",
    }
    #: 20 notes and 3 boards read; the three bad notes were never notes.
    assert report["counts"] == {"files": 1, "read": 23, "written": 23, "skipped": 5, "merged": 0, "documents": 5}


def test_the_report_is_reachable_from_the_activity_panel(client, folder_with_bad_files):
    data, _ = folder_with_bad_files
    activity.clear()
    report_id = client.post("/import/app?source=memorymap", files=[("files", ("n.zip", data, "application/zip"))]).json()["report"]
    #: The finished list carries every run that ended (INBOX 805); the
    #: import's is the one with a report, listed once.
    finished = [row for row in client.get("/activity").json()["finished"] if row.get("report")]
    assert [row["report"] for row in finished] == [report_id]
    assert "imported 23 notes" in finished[0]["detail"]
    assert client.get("/import/reports/../../etc").status_code == 404
    assert client.get("/import/reports/20260101-000000000000-nope").status_code == 404


def test_a_second_import_reports_the_notes_as_merged(client, folder_with_bad_files):
    data, _ = folder_with_bad_files
    files = [("files", ("n.zip", data, "application/zip"))]
    client.post("/import/app?source=memorymap", files=files)
    again = client.post("/import/app?source=memorymap", files=files).json()
    assert again["counts"]["merged"] == 23 and again["counts"]["written"] == 0


def _vault(count: int) -> list[tuple[str, bytes]]:
    return [(f"Vault/Folder {i % 20}/note {i}.md", f"Note {i} of the big vault.\n".encode()) for i in range(count)]


def test_5000_files_list_report_per_100_and_stop_within_2_seconds(app_state, session):
    files = _vault(5000)
    t0 = time.perf_counter()
    read = app_import.read("obsidian", files, parse_frontmatter=_parse_frontmatter)
    listed = time.perf_counter() - t0
    assert len(read.notes) == 5000 and read.skipped == []
    steps: list[int] = []
    asked = threading.Event()
    job = activity.start("import", "Importing from Obsidian", stoppable=True)

    def step(done: int, total: int) -> None:
        steps.append(done)
        if done == 300:
            asked.set()

    progress = export_folder.Progress(stopped=lambda: job.stopped, step=step)
    out: dict = {}
    worker = threading.Thread(target=lambda: out.update(app_import.write(session, "obsidian", read.notes, progress)))
    worker.start()
    assert asked.wait(120), "the import never reached 300 notes"
    stop_at = time.perf_counter()
    assert activity.stop(job.id)[0]
    worker.join(30)
    landed = time.perf_counter() - stop_at
    activity.finish(job)
    print(f"\n5,000 files listed in {listed:.2f} s; Stop landed in {landed:.3f} s after {out['imported']} notes")
    assert landed < 2.0
    assert out["stopped"] is True
    assert steps[:3] == [100, 200, 300]
    kept = session.query(Entry).filter(Entry.source_path.like("obsidian:%")).count()
    assert kept == out["imported"] and 300 <= kept < 5000


def test_the_background_jobs_overview_carries_the_last_import_report(client, folder_with_bad_files):
    """Ledger 1406: the overview's import row offers a Report button."""
    data, _ = folder_with_bad_files
    before = {r["kind"]: r for r in client.get("/jobs/last-runs").json()["jobs"]}
    assert "report" not in before["import"]
    body = client.post("/import/app?source=memorymap", files=[("files", ("notebook.zip", data, "application/zip"))]).json()
    after = {r["kind"]: r for r in client.get("/jobs/last-runs").json()["jobs"]}
    assert after["import"]["report"] == body["report"]
