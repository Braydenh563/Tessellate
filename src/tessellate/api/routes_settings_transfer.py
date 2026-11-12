"""Export and import routes of the notebook: backup, JSON, markdown, CSV, folder and document imports.

Split out of routes_settings.py (K24); mounted in app.py beside that module's router.
"""

from __future__ import annotations

import csv
import io
import hashlib
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate import __version__
from tessellate.core import backup_bundle, deps, jobruns, jobs, logbuffer, paths
from tessellate.core.database import Entry, utcnow
from tessellate.core.deps import get_session
from tessellate.entry import importer, manager
from tessellate.entry import manager_wiki
from tessellate.entry import manager_text
from tessellate.repo import categories as categories_repo
from tessellate.repo import relation_types, relations
from tessellate.repo.content import walk as content_walk
from tessellate.entry.cleantext import import_path
from tessellate.api.this_computer import this_computer_only

router = APIRouter(tags=["settings"])


def _export_rows(session: Session) -> tuple[list, list[Entry], list]:
    """Everything the user owns, including binned entries, an export
    should never silently drop data. The notes and boards come from the one
    export walker (`repo/content.walk`), the folder export's own."""
    categories = categories_repo.all_rows(session)
    entries = [row for _adapter, row in content_walk(session, ("note", "board"))]
    links = relations.all_rows(session)
    return categories, entries, links



@router.get("/export/backup")
def export_backup(background_tasks: BackgroundTasks):
    import os
    config = deps.get_config()
    fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="memorymap_backup_")
    os.close(fd)

    def cleanup():
        try:
            os.remove(tmp_path)
        except OSError:
            pass  # already gone, or never got written, nothing left to clean up

    background_tasks.add_task(cleanup)
    #: **A snapshot, not the live file** (audit 2026-10-05, ARCH-18): the
    #: database runs in WAL mode, so zipping the main file alone lost what
    #: was saved last (measured, three notes and none of them in the zip,
    #: with `integrity_check` passing). `backup_bundle.build_zip` copies a
    #: consistent whole through SQLite's backup API, and adds `uploads/` to
    #: `media/`. The same zip is what `POST /backups/bundle` seals with a
    #: password and `POST /backups/bundle/restore` reads back.
    backup_bundle.build_zip(config.data_dir, config.db_path, Path(tmp_path))
    return FileResponse(tmp_path, media_type="application/zip", filename="memorymap_backup.zip", background=background_tasks)

@router.get("/export/json")

def export_json(session: Session = Depends(get_session)) -> Response:
    categories, entries, links = _export_rows(session)
    payload = {
        "app": "Tessellate",
        "version": __version__,
        "exported_at": utcnow().isoformat(),
        "categories": [{"id": c.id, "name": c.name} for c in categories],
        "entries": [],
        "links": [],
    }

    category_names = manager.bulk_category_names(session, entries)

    for e in entries:
        payload["entries"].append({
            "id": e.id,
            # Exports decrypt while the app is unlocked. An export is for
            # taking your notes elsewhere, and ciphertext with no key is
            # not your notes. (The app's own backups keep private notes
            # encrypted, and since SEC-03 carry none of their words in the
            # search index either: `backup.strip_leftovers`.)
            "content": manager_text.readable_content(e),
            "category": category_names.get(e.category_id, manager.UNCATEGORISED),
            "tags": manager.shown_tags(e),
            "ai_confidence": e.ai_confidence,
            # Said, so a note decrypted for the export is not mistaken for an
            # ordinary one by whatever reads the file next (SEC-14).
            "is_private": bool(e.is_private),
            "created_at": e.created_at.isoformat(),
            "updated_at": e.updated_at.isoformat(),
            # `is_deleted` is not decoration and not derivable from
            # `deleted_at`: an export is what a re-import reads, and without
            # this flag every note in the recycle bin comes back as a live
            # note. It went missing when this block was rewritten as a loop.
            "is_deleted": e.is_deleted,
            "deleted_at": e.deleted_at.isoformat() if e.deleted_at else None,
            #: A board or map keeps a companion entry the list hides; it is in
            #: the file as a note, so the file says which ones are those (1031
            #: SH8: the file held 210 where the list held 207).
            "is_board": bool(e.is_board),
        })

    payload["links"] = [
        {
            "id": link.id,
            "source_entry_id": link.source_entry_id,
            "target_entry_id": link.target_entry_id,
            # GRAPH_PLAN KG3: a link is its kind, its reason and its
            # properties as much as its two ends.
            "reason": link.reason,
            "link_type": link.link_type,
            "props": link.props,
        }
        for link in links
    ]
    payload["relation_types"] = [
        {k: v for k, v in kind.items() if k != "description"}
        for kind in relation_types.kinds(session).values()
    ]
    manager.log_action(session, "exported", "data", detail="json")
    session.commit()
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=tessellate-export.json"},
    )


def build_markdown_export(session: Session, ids: list[int] | None = None) -> bytes:
    """The zip itself, as bytes, with nothing HTTP about it.

    Lifted out of the route below so `python -m tessellate --export PATH`
    writes exactly the same archive the Settings button downloads, rather
    than a second implementation that drifts. uninstall.sh and
    uninstall.bat call that entry point for `--export`, which is the whole
    point: someone removing the app should be able to take their notes out
    first, from a terminal, with no browser and no running server.

    The audit line is written here rather than in the route so a CLI export
    is recorded too: "where did this zip come from" is the same question
    either way.
    """
    _categories, entries, _links = _export_rows(session)
    #: A selection (WORLD_CLASS_PLAN 5 item 6, section 8 row 30): the same
    #: files the whole export writes, for these notes only.
    if ids is not None:
        wanted = set(ids)
        entries = [entry for entry in entries if entry.id in wanted]
    category_names = manager.bulk_category_names(session, entries)
    
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            cat_name = category_names.get(entry.category_id, manager.UNCATEGORISED)
            folder = (
                "_recycle-bin"
                if entry.is_deleted
                else paths.slug(cat_name)
            )
            tags = manager.entry_tags(entry)
            front = [
                "---",
                f"category: {cat_name}",
                f"created: {entry.created_at.isoformat()}",
            ]
            if tags:
                front.append(f"tags: [{', '.join(tags)}]")
            if entry.pinned:
                front.append("pinned: true")
            readable = manager_text.readable_content(entry)
            #: KG4: the note's own properties join the app's in one block.
            from tessellate.entry import properties as note_properties

            end = note_properties.block_end(readable)
            if end:
                front.extend(line for line in readable[:end].rstrip("\n").split("\n")[1:-1] if line.strip())
                readable = readable[end:].lstrip("\n")
            front.append("---")
            body = "\n".join(front) + f"\n\n{readable}\n"
            archive.writestr(f"{folder}/{entry.id}-{paths.slug(readable, 30)}.md", body)
    detail = "markdown" if ids is None else f"markdown, {len(entries)} selected"
    manager.log_action(session, "exported", "data", detail=detail)
    session.commit()
    return buffer.getvalue()


@router.get("/export/markdown")
def export_markdown(
    session: Session = Depends(get_session),
    ids: str = Query(default="", max_length=6000, description="Comma-separated note ids; empty for every note"),
) -> Response:
    """A zip of Obsidian-friendly .md files: one file per note, one
    folder per category, YAML frontmatter carrying the metadata. Binned
    notes go under _recycle-bin/, exports never silently drop data. With
    `ids`, only those notes (the Notes selection's Export)."""
    chosen = [int(part) for part in ids.split(",") if part.strip().isdigit()] if ids.strip() else None
    return Response(
        content=build_markdown_export(session, chosen),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=tessellate-markdown.zip"},
    )


MAX_IMPORT_BYTES = 1024 * 1024  # a single markdown note, not a novel
#: `import_markdown` below had a per-file size cap but no cap on how many
#: files one request could carry, each one does its own `create_entry` +
#: `session.commit()`, so a request with an unbounded file count ran
#: unbounded work. Same instinct as `MAX_DOCUMENT_IMPORT_NOTES` just below:
#: a real "import my Obsidian vault" drag-and-drop is at most a few hundred
#: files, so this is generous headroom, not a real-world ceiling.
MAX_IMPORT_FILES = 500


#: The keys the app reads into its own fields (and writes on export); every
#: other key stays in the note's text as a property (GRAPH_PLAN KG4).
_APP_KEYS = {"category", "tags", "created", "updated", "pinned"}


def _exported_created(values: list[str] | None):
    """The `created:` the export wrote, as the naive UTC the database holds,
    or None when it is absent, unreadable, or in the future (a vault from
    elsewhere may use any date format; only a clean past ISO stamp is trusted)."""
    from datetime import datetime, timezone

    if not values:
        return None
    try:
        parsed = datetime.fromisoformat(values[0].strip())
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed if parsed <= datetime.now(timezone.utc).replace(tzinfo=None) else None


def _keep_exported_state(session: Session, entry, meta: dict) -> None:
    """Put back the date and pin an exported note carried."""
    if meta.get("created"):
        entry.created_at = meta["created"]
    if meta.get("pinned"):
        entry.pinned = True
    if meta.get("created") or meta.get("pinned"):
        session.commit()


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """(metadata, content). `category` and `tags` become the note's own
    fields; `created` and `updated` are the export's and are dropped; every
    other key stays at the top of the note as its properties (KG4), lines
    as written, so an imported vault keeps them. Imports must never eat
    someone's text."""
    from tessellate.entry import properties as note_properties

    end = note_properties.block_end(text)
    if not end:
        return {}, text
    found, body = note_properties.split(text)
    meta: dict = {}
    if found.get("category"):
        meta["category"] = found["category"][0]
    if "tags" in found:
        meta["tags"] = [t for t in found["tags"] if t]
    # What this app's own export wrote (audit 2026-10-10, item 1): a note
    # exported and imported again kept its words and lost its date and pin,
    # so the timeline reshuffled to "everything today".
    stamp = _exported_created(found.get("created"))
    if stamp is not None:
        meta["created"] = stamp
    if (found.get("pinned") or [""])[0].lower() == "true":
        meta["pinned"] = True
    kept: list[str] = []
    skipping = False
    for line in text[:end].rstrip("\n").split("\n")[1:-1]:
        head = line.partition(":")[0].strip().lower()
        if line[:1] not in (" ", "\t", "-") and ":" in line:
            skipping = head in _APP_KEYS
        if not skipping:
            kept.append(line)
    body = body.lstrip("\n")
    if any(line.strip() for line in kept):
        return meta, "---\n" + "\n".join(kept) + "\n---\n" + body
    return meta, body



class ImportDirectoryRequest(BaseModel):
    path: str

def _validated_import_directory(path_value: str) -> Path:
    """The one place `import_directory`'s request path is turned into a
    real, checked filesystem path, both the route and the background job
    it schedules use this, and both pass its *return value* on, never the
    original string.

    CodeQL flags the raw `req.path` reaching file I/O as "uncontrolled
    data used in a path expression", correct about the data flow, but
    this route's whole job is letting the already-authenticated owner of
    this single-user, local-only notebook pick any folder on their own
    machine to import from (the Obsidian-vault-import feature). There is
    no narrower base directory to confine it to without breaking that.
    What this *can* do, and didn't before: reject a null byte outright
    (the one thing no legitimate path contains), confirm the path
    genuinely resolves to an existing directory before anything reads
    from it, and, the part a first pass at this missed, make sure the
    resolved, checked `Path` is what actually gets used downstream rather
    than the original unchecked string living on past this function.
    """
    if not path_value or "\x00" in path_value:
        raise ValueError("Invalid directory path")
    # Normalised with `realpath` and confined by a prefix test before the
    # disk is touched at all: the form CodeQL's path-injection query knows
    # as a guard (a `Path.resolve(strict=True)` first is itself a read of
    # an unchecked path, and `is_relative_to` is not recognised).
    # The guard is spelled out here rather than behind a helper: CodeQL only
    # counts a `startswith` that sits in the same function as the read.
    real = os.path.normpath(os.path.realpath(path_value))
    root = _import_root_for(real)
    if not root or not real.startswith(root):
        raise ValueError("Outside the folders an import may read")
    p = Path(real)
    if not p.is_dir():
        raise ValueError("Invalid directory path")
    # **Inside home or the data folder, judged after `resolve`** (WORLD_CLASS
    # _PLAN §12, S3). "There is no narrower base directory" above was written
    # for the owner at their own keyboard; for anyone holding a token over a
    # network, this route was a read of any folder the server can see. Home
    # is where a vault lives; the data folder is where the app itself puts
    # things. Checked on the resolved path, so a symlink in home that points
    # at `/etc` is judged by where it lands, not by where it sits.
    return p


def _import_roots() -> list[str]:
    """The folders a directory import may read from, as real paths."""
    roots = []
    for candidate in (Path.home(), deps.get_config().data_dir):
        try:
            roots.append(os.path.realpath(candidate))
        except OSError:
            continue
    return roots


def _under_root(real: str, root: str) -> bool:
    """Is the real path `real` the folder `root` or somewhere inside it?"""
    return real == root or real.startswith(root.rstrip(os.sep) + os.sep)


def _import_root_for(real: str) -> str:
    """The import root `real` lies in (separator-aware), or "" for none."""
    for root in _import_roots():
        if _under_root(real, root):
            return root
    return ""


def _inside(root: Path, f: Path) -> bool:
    """Does `f`, symlinks followed, still lie inside `root`?

    The walk below reads every `.md` under the chosen folder, and a symlink
    inside it can point anywhere: `innocent.md -> ~/.ssh/config.md`, or a
    linked folder. The folder was checked; what it links to was not, so
    each file is checked by where it resolves.
    """
    real = os.path.realpath(f)
    return _under_root(real, os.path.realpath(root)) and os.path.isfile(real)


def _run_directory_import(directory_path: str):
    """The background task: the import, recorded as the last "import" run
    (INBOX 438), because a 202 Accepted answers nobody about how it went."""
    with jobruns.job_run("import", origin="you") as run:
        _import_directory_files(directory_path, run)


#: Stands for "this path is a private note": matched without its text.
_PRIVATE = object()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _already_imported(session) -> dict:  # noqa: ANN001
    """Every live note that came from a vault file: its path in the vault ->
    the hashes of its text, or `_PRIVATE` when its text is encrypted."""

    from tessellate.core.database import Entry

    known: dict = {}
    rows = session.execute(
        select(Entry.source_path, Entry.content, Entry.is_private).where(
            Entry.source_path != "", Entry.is_deleted.is_(False)
        )
    )
    for path, content, private in rows:
        if private:
            known[path] = _PRIVATE
        elif known.get(path) is not _PRIVATE:
            known.setdefault(path, set()).add(_text_hash((content or "").strip()))
    return known


def _directory_import_detail(imported: int, already: int, skipped: int, skipped_oversize: int) -> str:
    """The activity line a folder import leaves: what came in, what was
    already in, and what was skipped and why."""
    detail = f"markdown dir x{imported}"
    if already:
        detail += f", {already} already in"
    if skipped:
        detail += f", skipped {skipped}"
        if skipped_oversize:
            detail += f" ({skipped_oversize} over {MAX_IMPORT_BYTES // (1024 * 1024)} MB)"
    return detail


def _import_directory_files(directory_path: str, run: "jobruns.Run"):
    try:
        p = _validated_import_directory(directory_path)
    except ValueError:
        run.fail("That folder is not inside your home folder or the data folder.")
        return
    with deps.get_db().session() as session:
        imported = 0
        skipped = 0
        skipped_oversize = 0
        already = 0
        made = []
        known = _already_imported(session)
        for f in p.rglob("*.md"):
            if not _inside(p, f):
                skipped += 1
                continue
            try:
                #: `import_markdown` (the upload path just below) has always
                #: capped a file at `MAX_IMPORT_BYTES` before reading it; this
                #: path read whole files with no ceiling at all, so a
                #: multi-gigabyte `.md` dropped into the vault by mistake was
                #: read into memory in full. `stat()` first and reuse the
                #: same constant, so a directory import can't be a bigger
                #: attack surface than the upload form sitting right next to
                #: it in the settings page.
                if f.stat().st_size > MAX_IMPORT_BYTES:
                    skipped += 1
                    skipped_oversize += 1
                    continue
                text = f.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(text)
                if not body.strip():
                    skipped += 1
                    continue
                try:
                    relative = f.relative_to(p).as_posix()[:500]
                except ValueError:
                    relative = f.name[:500]
                #: **Running it again is safe** (SEC-10, audit 2026-10-05): a
                #: file whose path in the vault and whose text are already a
                #: note is passed over, so "import again" finishes an import
                #: that was cut off instead of doubling what got in. A note
                #: made private since is matched on its path alone: its text
                #: is encrypted, and a second, readable copy is the one thing
                #: an import must never make of it.
                seen = known.get(relative)
                if seen is not None and (seen is _PRIVATE or _text_hash(body.strip()) in seen):
                    already += 1
                    continue
                #: **The file's own text, unchanged.** An earlier attempt at
                #: this prepended `# <filename>` so the note would carry its
                #: vault name: and three existing tests caught it, rightly:
                #: an importer that edits what it imports is a data-loss bug
                #: waiting to be reported, and this app's own rule is that a
                #: note has no separate title, its opening words *are* its
                #: name. The filename is preserved on `source_path` instead,
                #: where `find_by_wiki_name` reads it, so `[[wiki links]]`
                #: resolve without a single character of the note changing.
                entry = manager.create_entry(
                    session,
                    body.strip(),
                    category_name=meta.get("category") or manager.UNCATEGORISED,
                    tags=meta.get("tags") or [],
                    ai_confidence=100 if meta.get("category") else 0,
                )
                #: Relative to the vault root, never absolute, see
                #: `Entry.source_path`. `as_posix` so a vault imported on
                #: Windows and one imported on Linux group identically.
                entry.source_path = relative
                if meta.get("category"):
                    entry.user_filed = True
                _keep_exported_state(session, entry, meta)
                deps.store_quietly(session, entry)
                imported += 1
                made.append(entry)
                known.setdefault(relative, set()).add(_text_hash(body.strip()))
                if imported % 50 == 0:
                    session.commit()
            except Exception:
                # Counted on the activity line below, and now said: which
                # file, and why. A skip used to be a number with no reason.
                logging.getLogger("tessellate.import").warning(
                    "skipped %s while importing a folder", f.name, exc_info=True
                )
                skipped += 1
                #: A failed flush leaves the session refusing every later
                #: statement until it is rolled back, so one bad file used to
                #: end the import for every file after it (SEC-10). Each note
                #: before it is already committed by `create_entry`.
                session.rollback()
        #: The importer runs as a background task (202 Accepted, no
        #: synchronous response), so a skipped file has nowhere to be
        #: reported except this activity-log line: unlike `import_markdown`,
        #: which can hand its skip list straight back in the response body,
        #: this is the only place the count and the reason reach anyone.
        #: Firing on `skipped` too, not just `imported`, matters here: a
        #: directory whose files were all oversize used to leave no trace
        #: at all, imported stayed 0 and the whole run vanished silently.
        _link_imported(session, made)
        if imported > 0 or skipped > 0 or already > 0:
            detail = _directory_import_detail(imported, already, skipped, skipped_oversize)
            manager.log_action(session, "imported", "data", detail=detail)
            session.commit()
            run.result = (
                f"imported {imported} note{'' if imported == 1 else 's'} from a folder"
                + (f", {already} already in" if already else "")
                + (f", skipped {skipped}" if skipped else "")
            )
            #: A whole vault arriving at once is exactly the "large change"
            #: the rebuild suggestion exists for, see `mark_index_stale`.
            if imported > 0:
                deps.mark_index_stale(imported)
        else:
            run.result = "no markdown files found in that folder"

@router.post("/import/directory", status_code=202, dependencies=[Depends(this_computer_only)])
def import_directory(req: ImportDirectoryRequest):
    try:
        p = _validated_import_directory(req.path)
    except ValueError:
        raise HTTPException(
            400,
            "Choose a folder that exists inside your home folder or the notebook's data folder.",
        ) from None
    # The validated, resolved path, not req.path, is what the background
    # job and the response both carry from here on.
    canonical_path = str(p)
    # On the pool, not a request task: the job is remembered, so a quit
    # part-way is finished at the next launch (Brief 9). One folder waiting
    # twice is one job.
    jobs.enqueue(
        "import", _run_directory_import, canonical_path, name=p.name, dedupe_key=("import", canonical_path)
    )
    return {"status": "started", "path": canonical_path}

@router.post("/import/markdown", status_code=201)

def import_markdown(
    files: list[UploadFile], session: Session = Depends(get_session)
) -> dict:
    """Turn uploaded .md files into notes (Obsidian-friendly: the same
    frontmatter the export writes is understood on the way back in)."""
    if len(files) > MAX_IMPORT_FILES:
        raise HTTPException(
            status_code=422,
            detail=f"{len(files)} files at once is more than one import handles "
            f"({MAX_IMPORT_FILES} max): split it into smaller batches.",
        )
    with jobruns.job_run("import", origin="you") as run:
        result = _import_markdown_files(files, session)
        run.result = f"imported {result['imported']} note{'' if result['imported'] == 1 else 's'}" + (
            f", skipped {len(result['skipped'])}" if result["skipped"] else ""
        )
    return result


def _link_imported(session: Session, entries: list) -> None:
    """Join up the `[[wiki links]]` an import brought in, both ways.

    After every file is a note, so a link to a file later in the same batch
    resolves (`sync_wiki_links` only links names that exist), and
    `resolve_links_to` links notes already here that named one of the new
    ones. Before this, an imported vault had no links at all until each note
    was saved again (tests/test_import_markdown_links.py)."""
    for entry in entries:
        manager_wiki.sync_wiki_links(session, entry)
        manager_wiki.resolve_links_to(session, entry)
    session.commit()


def _import_markdown_files(files: list[UploadFile], session: Session) -> dict:
    imported = 0
    skipped: list[str] = []
    #: The notes this import made, so the client's Undo can bin exactly
    #: these (INBOX 464 (18): choosing the files starts the import now).
    ids: list[int] = []
    made = []
    #: **Choosing the same files again adds nothing** (the folder importer's
    #: rule, SEC-10, and the README's promise): a file whose name or path and
    #: whose text are already a note is passed over; an edited one comes in.
    known = _already_imported(session)
    already = 0
    for file in files:
        raw = file.file.read(MAX_IMPORT_BYTES + 1)
        name = file.filename or "note.md"
        if len(raw) > MAX_IMPORT_BYTES:
            skipped.append(f"{name}: larger than 1 MB")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append(f"{name}: not a text file")
            continue
        meta, body = _parse_frontmatter(text)
        if not body.strip():
            skipped.append(f"{name}: empty")
            continue
        #: The path, not the text, see the directory importer above for why
        #: nothing here rewrites the file's own content. A browser sends the
        #: relative path as the filename when the picker was a directory
        #: picker, and the bare name otherwise; both are relative, which is
        #: the only kind stored.
        relative = import_path(name, "imported.md")
        seen = known.get(relative)
        if seen is not None and (seen is _PRIVATE or _text_hash(body.strip()) in seen):
            already += 1
            continue
        entry = manager.create_entry(
            session,
            body.strip(),
            category_name=meta.get("category") or manager.UNCATEGORISED,
            tags=meta.get("tags") or [],
            ai_confidence=100 if meta.get("category") else 0,
        )
        entry.source_path = relative
        if meta.get("category"):
            entry.user_filed = True  # the file said where it belongs
            session.commit()
        _keep_exported_state(session, entry, meta)
        deps.store_quietly(session, entry)
        imported += 1
        ids.append(entry.id)
        made.append(entry)
        known.setdefault(relative, set()).add(_text_hash(body.strip()))
    _link_imported(session, made)
    detail = f"markdown x{imported}" + (f", {already} already in" if already else "")
    manager.log_action(session, "imported", "data", detail=detail)
    session.commit()
    deps.mark_index_stale(imported)
    return {"imported": imported, "skipped": skipped, "ids": ids, "already": already}


#: A PDF or slide deck, not a video, well past what a document-conversion
#: library is for.
MAX_DOCUMENT_IMPORT_BYTES = 20 * 1024 * 1024
#: A very long deck splits into one note per slide; a sane ceiling on how
#: many notes one upload can create, the same instinct as `tools.py`'s
#: MAX_PLAN_STEPS: a huge number here is usually a converter emitting one
#: heading per page rather than someone wanting 200 new notes at once.
MAX_DOCUMENT_IMPORT_NOTES = 25


@router.post("/import/document", status_code=201)
def import_document(file: UploadFile, session: Session = Depends(get_session)) -> dict:
    """Turn an uploaded PDF/Word/slide file into one or more notes, via
    markitdown (§37G): the button `core/extras.py`'s `documents` extra
    installed for and had nothing behind, until this.

    One note per top-level heading when the converted markdown has more than
    one (a deck, a document with real chapters); the whole file as one note
    otherwise: `import_markdown`'s "each file becomes a note" for the common
    case, once markitdown has turned it into something with that shape.
    """
    if not importer.markitdown_available():
        raise HTTPException(status_code=503, detail=importer.INSTALL_HINT)

    data = file.file.read(MAX_DOCUMENT_IMPORT_BYTES + 1)
    if len(data) > MAX_DOCUMENT_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="That file is larger than 20 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="That file is empty.")

    suffix = Path(file.filename or "document").suffix[:12] or ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as saved:
        saved.write(data)
        saved.flush()
        try:
            text = importer.convert_to_markdown(Path(saved.name))
        except Exception as exc:  # a file markitdown can't parse must not 500
            #: Background jobs shows this row to a person, so it is a plain
            #: sentence with the file's name; the converter's own words (a
            #: path, a library's message) stay in the log with the traceback
            #: (final scan, item 5).
            jobruns.note_finished(
                "import",
                "failed",
                f"Couldn't read {logbuffer.safe_value(file.filename or 'that file', 80)}. "
                "It may be damaged or in a format that can't be converted.",
            )
            logging.getLogger("tessellate.import").warning(
                "couldn't convert %s", logbuffer.safe_value(file.filename, 80), exc_info=True
            )
            raise HTTPException(
                status_code=422,
                detail="Couldn't read that file. It may be damaged or in a format that can't be converted.",
            ) from exc

    all_sections = importer.split_into_sections(text)
    if not all_sections:
        jobruns.note_finished(
            "import", "failed", f"{file.filename or 'That file'} had no readable text in it"
        )
        raise HTTPException(
            status_code=422, detail="That file had no readable text in it."
        )
    sections = all_sections[:MAX_DOCUMENT_IMPORT_NOTES]

    with jobruns.job_run("import", origin="you") as run:
        ids = _create_document_notes(session, sections, Path(file.filename or "document").name)
        imported = len(ids)
        run.result = f"imported {imported} note{'' if imported == 1 else 's'} from {file.filename or 'a document'}"
    manager.log_action(
        session, "imported", "data", detail=f"document x{imported} ({file.filename})"
    )
    session.commit()
    return {
        "imported": imported,
        "truncated": len(all_sections) > len(sections),
        "filename": file.filename,
        "ids": ids,
    }


def _create_document_notes(session: Session, sections: list[str], source_name: str = "") -> list[int]:
    """The ids of the notes made, one per section (the client's Undo bins
    exactly these). Each keeps the file's name as its `source_path`, as the
    other importers do, which is also what marks it as text from outside for
    the agent's injection guard (SEC-02)."""
    ids: list[int] = []
    for section in sections:
        entry = manager.create_entry(
            session,
            section,
            category_name="Imports",
            tags=["imported"],
            ai_confidence=100,
        )
        entry.user_filed = True  # this file said where it came from, not the janitor
        entry.source_path = import_path(source_name, "document")
        session.commit()
        deps.store_quietly(session, entry)
        ids.append(entry.id)
    return ids



# web search (routes_websearch.py) and backups (routes_backups.py) moved out

@router.get("/export/csv")
def export_csv(session: Session = Depends(get_session)) -> Response:
    _categories, entries, _links = _export_rows(session)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "content", "category", "tags", "ai_confidence", "created_at", "is_deleted"]
    )
    
    category_names = manager.bulk_category_names(session, entries)
    
    for e in entries:
        writer.writerow(
            [
                e.id,
                manager_text.readable_content(e),
                category_names.get(e.category_id, manager.UNCATEGORISED),
                "|".join(manager.shown_tags(e)),
                e.ai_confidence,
                e.created_at.isoformat(),
                e.is_deleted,
            ]
        )
    manager.log_action(session, "exported", "data", detail="csv")
    session.commit()
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tessellate-export.csv"},
    )
