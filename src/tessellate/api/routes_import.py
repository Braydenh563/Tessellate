"""`POST /import/app`: notes from Notion, Obsidian, Evernote or Apple Notes
(WORLD_CLASS_PLAN H6, row 25). The readers and the writer are
`entry/app_import.py`; this is the door, the size caps and the job line.

Two calls, the preview step (INBOX 1520): `dry_run=1` reads and lists what
would come in and writes nothing; the run then carries the keys the person
unticked as `exclude`. The answer carries the ids so the toast's Undo can bin
exactly these notes.
"""

from __future__ import annotations

import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import BinaryIO

import json

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from tessellate.core import activity, deps, jobruns
from tessellate.core.deps import get_session
from tessellate.entry import app_import, export_folder, import_report, manager

router = APIRouter(tags=["import"])

#: Files in one request: a vault picked as a folder is many files.
MAX_FILES = 5000
#: Notes embedded and committed per call after an import (was one commit per note, L508).
EMBED_BATCH_NOTES = 100


def _received(files: list[UploadFile]) -> list[tuple[str, BinaryIO]]:
    """The uploads as the spooled files Starlette already wrote (K34): sized
    by seeking, never read whole here; `app_import.expand` opens a zip from
    the file and reads one member at a time."""
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=422, detail=f"{len(files)} files at once is more than one import takes ({MAX_FILES}).")
    raw: list[tuple[str, BinaryIO]] = []
    total = 0
    for upload in files:
        total += app_import.size_of(upload.file)
        if total > app_import.MAX_ARCHIVE_BYTES:
            raise HTTPException(status_code=413, detail="That export is larger than 200 MB.")
        raw.append((upload.filename or "note", upload.file))
    return raw


def _progress(run: jobruns.Run, job: activity.Job) -> export_folder.Progress:
    """The writer's reports, to both lines: the Background jobs record and
    the Activity row with its Stop."""

    def step(done: int, total: int) -> None:
        run.step(done, total, "Writing notes")
        job.update(done, total, f"{done} of {total} notes")

    return export_folder.Progress(stopped=lambda: job.stopped, step=step)


def _summary(written: dict, label: str) -> str:
    made = written["imported"]
    return f"imported {made} note{'' if made == 1 else 's'} from {label}" + (
        f", {written['already']} already here" if written["already"] else "")


def _excluded(text: str) -> set[str]:
    """The keys the preview's person unticked: a JSON list, refused whole when
    it is anything else, before a byte is read or written."""
    if not text:
        return set()
    try:
        keys = json.loads(text)
    except ValueError:
        keys = None
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise HTTPException(status_code=422, detail="The list of notes to leave out did not read.")
    return set(keys)


def _refuse_open_private_while_locked(source: str, notes: list) -> None:
    """A Tessellate folder exported unlocked carries its private notes readable,
    flagged `is_private`. Written while this notebook's private notes are locked
    there is no key to seal them with, and they landed as ordinary notes, words
    open and indexed (sm-1111 row 8). Refused before a note is made; sealed ones
    (exported locked) are fine, they stay sealed."""
    from tessellate.core import vault

    if source != "memorymap" or vault.key() is not None:
        return
    if any(n.record.get("is_private") and not n.record.get("sealed") for n in notes):
        raise HTTPException(status_code=409, detail="Some of these notes are private. Unlock private notes, then import again.")


@router.post("/import/app", status_code=201)
def import_app(
    files: list[UploadFile],
    response: Response,
    source: str = Query(pattern="^(notion|obsidian|evernote|apple|memorymap)$"),
    dry_run: bool = Query(False),
    exclude: str = Form(""),
    session: Session = Depends(get_session),
) -> dict:
    """Read, write, and keep a report. The write is a job with progress and
    Stop (decision 70): Stop ends it at the next note and every note made
    before then stays: the writer commits every hundred notes and at a stop,
    and the embeddings are stored and committed in batches (L508)."""
    from tessellate.api.routes_settings_transfer import _parse_frontmatter

    left_out = _excluded(exclude)
    raw = _received(files)
    label = app_import.LABELS[source]
    t0 = time.perf_counter()
    try:
        read = app_import.read(source, raw, parse_frontmatter=_parse_frontmatter)
    except app_import.TooBig as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    if dry_run:
        response.status_code = 200  # nothing was made
        return {"source": source, "label": label, "found": len(read.notes), "skipped": read.skipped[:50],
                **app_import.preview(session, source, read.notes)}
    read.notes = [note for note in read.notes if note.key not in left_out]
    _refuse_open_private_while_locked(source, read.notes)
    with jobruns.job_run("import", title=f"Importing from {label}", origin="you") as run, activity.track(
        "import", f"Importing from {label}", ledger=False
    ) as job:
        job.update(0, len(read.notes), f"0 of {len(read.notes)} notes")
        progress = _progress(run, job)
        if source == "memorymap":
            written = export_folder.write(session, read, deps.get_config().uploads_dir, progress)
        else:
            written = app_import.write(session, source, read.notes, progress)
        made = written.pop("entries")
        for start in range(0, len(made), EMBED_BATCH_NOTES):
            if job.stopped:  # Stop is honoured between batches; the notes are already kept
                break
            deps.store_quietly_many(session, made[start : start + EMBED_BATCH_NOTES])
        run.result = _summary(written, label)
        if written.get("stopped"):
            run.cancel(f"stopped: {run.result}")
        report = import_report.build(source=source, label=label, files=len(raw), read=read, written=written,
                                     seconds=time.perf_counter() - t0, stopped=bool(written.get("stopped")))
        job.report = import_report.save(deps.get_config().data_dir, report)
        job.result = run.result
        job.label = f"Import from {label}"  # the finished line's name
    manager.log_action(session, "imported", "data", detail=f"{source} x{written['imported']}")
    session.commit()
    if written["imported"]:
        deps.mark_index_stale(written["imported"])
    written.pop("idmap", None)
    written.pop("said", None)
    return {**written, "skipped": read.skipped[:50], "source": source, "found": len(read.notes),
            "report": job.report, "counts": report["counts"]}


@router.get("/import/reports/{report_id}")
def import_report_page(report_id: str) -> dict:
    """One import's report: the counts and every skipped item with its reason."""
    found = import_report.load(deps.get_config().data_dir, report_id)
    if found is None:
        raise HTTPException(status_code=404, detail="That import report is no longer kept.")
    return found


@router.get("/export/folder")
def export_notebook_folder(background_tasks: BackgroundTasks, session: Session = Depends(get_session)) -> FileResponse:
    """The whole notebook as a markdown folder in a zip (WORLD_CLASS 25b):
    every note with its sidecar and attachments, documents, boards and an
    `index.json`. Written to a temporary file, not memory, because the
    attachments can be large; the file is removed once it is sent."""
    handle, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="memorymap_folder_")
    os.close(handle)
    background_tasks.add_task(lambda: Path(tmp_path).unlink(missing_ok=True))
    uploads_dir = deps.get_config().uploads_dir
    with jobruns.job_run("export", origin="you") as run, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as archive:
        done = export_folder.export(session, uploads_dir, archive, progress=lambda n, total: run.step(n, total, "Writing notes"))
        counts = done.manifest["counts"]
        run.result = f"exported {counts['notes']} notes, {counts['attachments']} attachments" + (
            f", {counts['missing']} attachment files missing" if counts["missing"] else "")
    manager.log_action(session, "exported", "data", detail="folder")
    session.commit()
    return FileResponse(tmp_path, media_type="application/zip", filename="tessellate-notebook.zip", background=background_tasks)
