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
import re
import secrets
import shutil
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, BinaryIO, Callable, Coroutine

import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from tessellate.core import activity, deps, jobruns
from tessellate.core.deps import get_session
from tessellate.entry import app_import, export_folder, import_report, manager

#: Files in one request: a vault picked as a folder is many files.
MAX_FILES = 5000
#: Notes embedded and committed per call after an import (was one commit per note, L508).
EMBED_BATCH_NOTES = 100
#: **Files sent in parts** (L-world-class-891): a 5,000-file vault was one
#: multipart body the page took 1.4s to build, twice (preview, then import).
#: Parts land in `data_dir/import-batches/<id>/` and the import reads them all
#: at once, so an Obsidian `[[link]]` resolves across parts. A batch left
#: behind (a closed tab) goes when the next one opens, a day on.
BATCH_DIR = "import-batches"
BATCH_KEEP_SECONDS = 24 * 3600
_BATCH_ID = re.compile(r"[0-9a-f]{32}")
_BATCH_LOCK = threading.Lock()


class _ManyFilesRoute(APIRoute):
    """Parses a multipart body with this import's own file cap before FastAPI
    reads it (L-world-class-411). Starlette refuses more than 1,000 file parts
    by default, so a folder of 5,000 notes got "Too many files" before
    `MAX_FILES` was read. The form is cached on the request, so FastAPI's own
    `request.form()` returns this one; one over the cap is let through so
    `_received` refuses it in the import's own words."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            if request.headers.get("content-type", "").startswith("multipart/form-data"):
                await request.form(max_files=MAX_FILES + 1)
            return await handler(request)

        return handle


router = APIRouter(tags=["import"], route_class=_ManyFilesRoute)


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


def _batch(batch_id: str) -> Path:
    """The staging folder of a batch; an id that is not one is the same 404 as a gone one."""
    folder = Path(deps.get_config().data_dir) / BATCH_DIR / batch_id
    if not _BATCH_ID.fullmatch(batch_id) or not folder.is_dir():
        raise HTTPException(status_code=404, detail="That import is no longer waiting. Choose the files again.")
    return folder


def _batch_list(folder: Path) -> list[list]:
    return json.loads((folder / "files.json").read_text(encoding="utf-8"))


@router.post("/import/app/batches", status_code=201)
def open_batch() -> dict:
    """A new batch, after clearing any left a day ago."""
    root = Path(deps.get_config().data_dir) / BATCH_DIR
    root.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - BATCH_KEEP_SECONDS
    for old in root.iterdir():
        if old.is_dir() and old.stat().st_mtime < cutoff:
            shutil.rmtree(old, ignore_errors=True)
    batch_id = secrets.token_hex(16)
    (root / batch_id).mkdir()
    (root / batch_id / "files.json").write_text("[]", encoding="utf-8")
    return {"batch": batch_id}


@router.post("/import/app/batches/{batch_id}")
def add_to_batch(batch_id: str, files: list[UploadFile]) -> dict:
    """One part: its files are copied to the batch in order, held to the same
    caps as one request (`MAX_FILES`, 200 MB) over every part."""
    folder = _batch(batch_id)
    with _BATCH_LOCK:
        staged = _batch_list(folder)
        if len(staged) + len(files) > MAX_FILES:
            raise HTTPException(status_code=422, detail=f"{len(staged) + len(files)} files at once is more than one import takes ({MAX_FILES}).")
        total = sum(size for _, size in staged)
        for upload in files:
            size = app_import.size_of(upload.file)
            total += size
            if total > app_import.MAX_ARCHIVE_BYTES:
                raise HTTPException(status_code=413, detail="That export is larger than 200 MB.")
            with open(folder / str(len(staged)), "wb") as out:
                shutil.copyfileobj(upload.file, out)
            staged.append([upload.filename or "note", size])
        (folder / "files.json").write_text(json.dumps(staged), encoding="utf-8")
    return {"files": len(staged)}


@router.delete("/import/app/batches/{batch_id}", status_code=204)
def drop_batch(batch_id: str) -> Response:
    """The preview's Cancel: nothing was imported, so nothing is kept."""
    shutil.rmtree(_batch(batch_id), ignore_errors=True)
    return Response(status_code=204)


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
    response: Response,
    files: list[UploadFile] = File(default_factory=list),
    source: str = Query(pattern="^(notion|obsidian|evernote|apple|memorymap)$"),
    dry_run: bool = Query(False),
    batch: str = Query(""),
    exclude: str = Form(""),
    session: Session = Depends(get_session),
) -> dict:
    """Read, write, and keep a report. The write is a job with progress and
    Stop (decision 70): Stop ends it at the next note and every note made
    before then stays: the writer commits every hundred notes and at a stop,
    and the embeddings are stored and committed in batches (L508). With
    `batch` the files are the ones its parts staged; the import (not the
    preview) clears them."""
    left_out = _excluded(exclude)
    if not batch:
        return _import(_received(files), response, source, dry_run, left_out, session)
    if files:
        raise HTTPException(status_code=422, detail="Send the files in the batch or in this request, not both.")
    folder = _batch(batch)
    raw = [(name, open(folder / str(i), "rb")) for i, (name, _) in enumerate(_batch_list(folder))]  # noqa: SIM115
    try:
        return _import(raw, response, source, dry_run, left_out, session)
    finally:
        for _, handle in raw:
            handle.close()
        if not dry_run:
            shutil.rmtree(folder, ignore_errors=True)


def _import(raw: list[tuple[str, BinaryIO]], response: Response, source: str, dry_run: bool, left_out: set[str],
            session: Session) -> dict:
    from tessellate.api.routes_settings_transfer import _parse_frontmatter

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
    return folder_zip(session, background_tasks, "tessellate-notebook.zip", "folder")


def folder_zip(session: Session, background_tasks: BackgroundTasks, filename: str, detail: str) -> FileResponse:
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
    manager.log_action(session, "exported", "data", detail=detail)
    session.commit()
    return FileResponse(tmp_path, media_type="application/zip", filename=filename, background=background_tasks)
