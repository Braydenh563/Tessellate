"""The whole notebook as a folder of markdown, and that folder back in
(WORLD_CLASS_PLAN 25b, Brief 48).

The other exports each answer one question: the JSON is the rows, the
markdown zip is notes for Obsidian, the backup is this app's own database.
None was a notebook a person could open in a file manager, read, and bring
back whole: attachments were left behind and dates, pins, links and
reminders were lost on the way in again. This writes, inside one zip:

    index.json                         the manifest: format, counts, every file
    notes/<category>/<id>-<title>.md   the note, front matter for what
                                       markdown cannot say
    notes/<category>/<id>-<title>.json the sidecar: every field of the note
    notes/<category>/<id>-<title>/...  its attachments, linked from the .md
    notes/_recycle-bin/...             binned notes, never silently dropped
    documents/<id>-<title>.md, .json   each document and its sidecar
    documents/_recycle-bin/...         binned documents, like binned notes
    boards/<id>-<title>.json           each board: its note and its canvas

**The sidecar wins.** On the way in (`read`, the "memorymap" source of
`app_import.read`) a note with a readable sidecar is restored from it field
by field; front matter is only the fallback for a note someone wrote by
hand into the folder. `ENTRY_LEFT_OUT` names every column the sidecar does
not carry and why, and a test fails when a new column is in neither list.

**Ids are this notebook's.** The import makes new rows and maps the old ids
to them (`idmap`), so links, reminders, a note's parent and a board's cards
point at the right notes in a notebook that already had others.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from tessellate.core import paths

FORMAT = "memorymap-folder"
VERSION = 1
MANIFEST = "index.json"
ATTACHMENTS_MARK = "<!-- memorymap:attachments -->"
BIN_FOLDER = "_recycle-bin"

#: Entry columns the sidecar does not carry, with the reason. Everything else
#: is written under its own name.
ENTRY_LEFT_OUT = {
    "id": "carried as the note's old id, mapped to a new one on import",
    "content": "carried as readable text",
    "category_id": "carried as the category's name",
    "tags": "carried as a list",
    "workspace_id": "a note lands in the space open when it is imported",
    "access_count": "how often this install opened it",
    "last_opened_at": "when this install last opened it",
    "entities_extracted_at": "a pass's bookmark; the pass reads the note again",
    "suggested_tags": "the filer's working state, worked out again",
    "filing_state": "the filer's working state",
    "filing_similar_id": "the filer's working state",
    "client_key": "the offline queue's key, unique to one install",
}
#: Sub-row columns never carried: their own ids (new on import) and the space.
_ROW_LEFT_OUT = {"id", "workspace_id"}


def _iso(value: object) -> object:
    return value.isoformat() if isinstance(value, datetime) else value


def _row(obj: object, left_out: set[str] | dict) -> dict:
    """Every column of a row as JSON-safe values, minus `left_out`."""
    return {
        column.name: _iso(getattr(obj, column.name))
        for column in obj.__table__.columns
        if column.name not in left_out
    }


def _parsed(name: str, value: object) -> object:
    """A sidecar value as the column holds it: every date column ends `_at`."""
    if name.endswith("_at") and isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return value


def _restore(obj: object, record: dict, skip: set[str] | dict) -> None:
    for column in obj.__table__.columns:
        if column.name in skip or column.name not in record:
            continue
        value = _parsed(column.name, record[column.name])
        if column.name == "deleted_at" and value is not None:
            # The bin clock restarts at the import: the stamp the export
            # carried is when the row was binned elsewhere, and the startup
            # sweep would purge a row just imported before it could be seen.
            value = datetime.now(timezone.utc)
        setattr(obj, column.name, value)


def _safe_name(name: str) -> str:
    base = posixpath.basename((name or "").replace("\\", "/"))
    cleaned = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "", base).strip(" .")
    return cleaned[:120] or "file"


def _sha1_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha1()  # noqa: S324  # an identity check, not security
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --- the records: one function per kind, shared by export and the round-trip test


def _readable(entry) -> tuple[str, bool]:  # noqa: ANN001
    """The note's text, and whether it is still sealed. A private note is
    exported readable while the vault is open (as the JSON export does);
    with it locked its sealed text is carried as is, so nothing is lost and
    nothing is opened."""
    from tessellate.core import crypto, vault
    from tessellate.entry import manager_text

    if crypto.is_encrypted(entry.content) and vault.key() is None:
        return entry.content, True
    return manager_text.readable_content(entry), False


def _attachment_names(attachments: list) -> list[str]:
    """One file name per attachment, unique within the note's folder."""
    names: list[str] = []
    for attachment in attachments:
        name = _safe_name(attachment.filename)
        stem, ext = posixpath.splitext(name)
        candidate, n = name, 2
        while candidate in names:
            candidate, n = f"{stem}-{n}{ext}", n + 1
        names.append(candidate)
    return names


def _attachment_record(attachment, name: str, uploads_dir: Path) -> dict:  # noqa: ANN001
    record = _row(attachment, _ROW_LEFT_OUT | {"entry_id", "stored_name"})
    record["file"] = name
    record["sha1"] = _sha1_file(uploads_dir / attachment.stored_name)
    return record


def _link_record(link) -> dict:  # noqa: ANN001
    return _row(link, _ROW_LEFT_OUT | {"source_entry_id"})


def _reminder_record(reminder) -> dict:  # noqa: ANN001
    return _row(reminder, _ROW_LEFT_OUT | {"entry_id", "document_id"})


@dataclass
class _Related:
    """Every row hanging off a note or document, fetched once per export."""

    category: dict = field(default_factory=dict)
    attachments: dict = field(default_factory=dict)
    links: dict = field(default_factory=dict)
    reminders: dict = field(default_factory=dict)
    doc_reminders: dict = field(default_factory=dict)
    doc_links: dict = field(default_factory=dict)


def _grouped(rows: list, key: str) -> dict:
    out: dict = {}
    for row in rows:
        out.setdefault(getattr(row, key), []).append(row)
    return out


def _related(session) -> _Related:  # noqa: ANN001
    from sqlalchemy import select

    from tessellate.core.database import Attachment, Category, DocumentLink, EntryLink, Reminder

    reminders = list(session.scalars(select(Reminder).order_by(Reminder.id)))
    return _Related(
        category={c.id: c.name for c in session.scalars(select(Category))},
        attachments=_grouped(list(session.scalars(select(Attachment).order_by(Attachment.id))), "entry_id"),
        links=_grouped(list(session.scalars(select(EntryLink).order_by(EntryLink.id))), "source_entry_id"),
        reminders=_grouped([r for r in reminders if r.entry_id is not None], "entry_id"),
        doc_reminders=_grouped([r for r in reminders if r.document_id is not None], "document_id"),
        doc_links=_grouped(list(session.scalars(select(DocumentLink).order_by(DocumentLink.id))), "document_id"),
    )


def note_record(entry, related: _Related, uploads_dir: Path) -> dict:  # noqa: ANN001
    """The sidecar of one note: every field, with what hangs off it."""
    from tessellate.entry import manager

    text, sealed = _readable(entry)
    # SEC-A2: a locked private note's files are plain bytes on disk; they stay out.
    attachments = [] if manager.note_is_sealed(entry.is_private) else related.attachments.get(entry.id, [])
    record = {"id": entry.id, "content": text, "sealed": sealed,
              "category": related.category.get(entry.category_id, manager.UNCATEGORISED),
              "tags": manager.entry_tags(entry)}
    record.update(_row(entry, ENTRY_LEFT_OUT))
    record["attachments"] = [
        _attachment_record(a, name, uploads_dir) for a, name in zip(attachments, _attachment_names(attachments))
    ]
    record["links"] = [_link_record(link) for link in related.links.get(entry.id, [])]
    record["reminders"] = [_reminder_record(r) for r in related.reminders.get(entry.id, [])]
    return record


def document_record(document, related: _Related) -> dict:  # noqa: ANN001
    record = {"id": document.id, **_row(document, _ROW_LEFT_OUT)}
    record["notes"] = [link.entry_id for link in related.doc_links.get(document.id, [])]
    record["reminders"] = [_reminder_record(r) for r in related.doc_reminders.get(document.id, [])]
    return record


def board_canvas(session, board_id: int) -> dict:  # noqa: ANN001
    """A board's cards, drawings and shapes. A shape's parent is named by its
    place in the list, since shape ids are new on import."""
    from sqlalchemy import select

    from tessellate.core.database import WhiteboardNode, WhiteboardObject, WhiteboardSketch

    def rows(model) -> list:  # noqa: ANN001
        return list(session.scalars(select(model).where(model.board_id == board_id).order_by(model.id)))

    objects = rows(WhiteboardObject)
    nodes, sketches = rows(WhiteboardNode), rows(WhiteboardSketch)
    place = {obj.id: i for i, obj in enumerate(objects)}
    shapes = []
    for obj in objects:
        record = _row(obj, _ROW_LEFT_OUT | {"board_id"})
        record["parent_id"] = place.get(obj.parent_id) if obj.parent_id is not None else None
        shapes.append(record)
    #: **A connector's two ends by place** (OPEN row 812): its data names the
    #: items it joins by id, and every id is new on import, so a connector
    #: came back joined to whatever had those numbers. Each end is also
    #: written as its kind and its place in that kind's list, which the import
    #: turns back into the new ids.
    places = {
        "node": {row.id: i for i, row in enumerate(nodes)},
        "object": place,
        "sketch": {row.id: i for i, row in enumerate(sketches)},
    }
    lines = []
    for sketch in sketches:
        record = _row(sketch, _ROW_LEFT_OUT | {"board_id"})
        ends = _link_ends(sketch.data, places)
        if ends:
            record["ends"] = ends
        lines.append(record)
    return {
        "nodes": [_row(node, _ROW_LEFT_OUT | {"board_id"}) for node in nodes],
        "sketches": lines,
        "objects": shapes,
    }


def _link_ends(data: str | None, places: dict) -> dict | None:
    """A connector's ends as {"source": [kind, place], ...}, or None for a
    drawing that joins nothing. An end on an item not on this board is left
    out, as it would be dangling either way."""
    try:
        parsed = json.loads(data or "")
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    ends = {}
    for side in ("source", "target"):
        item = parsed.get(f"{side}Id")
        if item is None:
            continue
        kind = parsed.get(f"{side}Kind") or "node"
        at = places.get(kind, {}).get(item)
        if at is not None:
            ends[side] = [kind, at]
    return ends or None


def snapshot(session, uploads_dir: Path) -> dict:  # noqa: ANN001
    """Every record the export writes, keyed by id: what the round-trip test
    compares, field by field, before and after. Rows come from the one
    export walker (`repo/content.walk`), as the export's do."""
    from tessellate.repo.content import walk

    related = _related(session)
    notes, boards, documents = {}, {}, {}
    for adapter, row in walk(session, ("note", "board", "document")):
        if adapter.kind == "document":
            documents[row.id] = document_record(row, related)
            continue
        record = note_record(row, related, uploads_dir)
        if adapter.kind == "board":
            record["canvas"] = board_canvas(session, row.id)
            boards[row.id] = record
        else:
            notes[row.id] = record
    return {"notes": notes, "boards": boards, "documents": documents}


# --- the export ------------------------------------------------------------------


def _front_matter(record: dict) -> tuple[list[str], str]:
    """The front matter lines and the body: the app's fields, then the note's
    own properties block folded into the same one (KG4), as the markdown
    export writes it."""
    from tessellate.entry import properties as note_properties

    front = ["---", f"category: {record['category']}", f"created: {record['created_at']}"]
    if record["tags"]:
        front.append(f"tags: [{', '.join(record['tags'])}]")
    if record.get("pinned"):
        front.append("pinned: true")
    text = record["content"]
    end = 0 if record["sealed"] else note_properties.block_end(text)
    if end:
        front.extend(line for line in text[:end].rstrip("\n").split("\n")[1:-1] if line.strip())
        text = text[end:].lstrip("\n")
    front.append("---")
    return front, text


def note_markdown(record: dict, folder_name: str) -> str:
    front, text = _front_matter(record)
    body = "\n".join(front) + f"\n\n{text}\n"
    if record["attachments"]:
        lines = [f"- [{a['file']}]({quote(folder_name)}/{quote(a['file'])})" for a in record["attachments"]]
        body += f"\n{ATTACHMENTS_MARK}\n" + "\n".join(lines) + "\n"
    return body


def _note_base(record: dict) -> str:
    folder = BIN_FOLDER if record.get("is_deleted") else paths.slug(record["category"])
    title = "private" if record["sealed"] else _front_matter(record)[1]  # the words, not a properties block
    return f"notes/{folder}/{record['id']}-{paths.slug(title)}"


def _write_note(archive: zipfile.ZipFile, record: dict, uploads_dir: Path, stored: dict) -> tuple[dict, list[str]]:
    """The note's three parts. Returns its manifest row and the attachments
    whose file was missing from the uploads folder."""
    base = _note_base(record)
    folder_name = posixpath.basename(base)
    archive.writestr(f"{base}.md", note_markdown(record, folder_name))
    archive.writestr(f"{base}.json", json.dumps(record, ensure_ascii=False, indent=1))
    files, missing = [], []
    for attachment in record["attachments"]:
        path = uploads_dir / stored[(record["id"], attachment["file"])]
        member = f"{base}/{attachment['file']}"
        if path.is_file():
            archive.write(path, member)
            files.append(member)
        else:
            missing.append(member)
    return {"id": record["id"], "md": f"{base}.md", "sidecar": f"{base}.json", "attachments": files}, missing


def _stored_names(related: _Related) -> dict:
    """(note id, exported file name) to the stored name in `uploads/`."""
    out = {}
    for entry_id, attachments in related.attachments.items():
        for attachment, name in zip(attachments, _attachment_names(attachments)):
            out[(entry_id, name)] = attachment.stored_name
    return out


@dataclass
class ExportResult:
    manifest: dict
    missing: list[str]
    seconds: float


def _categories(session) -> list[dict]:  # noqa: ANN001
    from sqlalchemy import select

    from tessellate.core.database import Category

    return [{"name": c.name, "description": c.description, "colour": c.colour}
            for c in session.scalars(select(Category).order_by(Category.id))]


def _write_documents(archive: zipfile.ZipFile, session, related: _Related) -> list[dict]:  # noqa: ANN001
    from tessellate.repo.content import walk

    rows = []
    for _adapter, document in walk(session, ("document",)):
        record = document_record(document, related)
        folder = f"documents/{BIN_FOLDER}" if document.deleted_at else "documents"
        base = f"{folder}/{document.id}-{paths.slug(document.title)}"
        archive.writestr(f"{base}.md", document.content or "")
        archive.writestr(f"{base}.json", json.dumps(record, ensure_ascii=False, indent=1))
        rows.append({"id": document.id, "md": f"{base}.md", "sidecar": f"{base}.json"})
    return rows


def export(session, uploads_dir: Path, archive: zipfile.ZipFile, progress=None) -> ExportResult:  # noqa: ANN001
    """Write the whole notebook into `archive`. `progress(done, total)` is
    called after every note, for the job's bar."""
    from tessellate import __version__
    from tessellate.repo.content import walk

    t0 = time.perf_counter()
    related = _related(session)
    stored = _stored_names(related)
    entries = list(walk(session, ("note", "board")))
    notes, boards, missing = [], [], []
    for done, (adapter, entry) in enumerate(entries, 1):
        record = note_record(entry, related, uploads_dir)
        if adapter.kind == "board":
            record["canvas"] = board_canvas(session, entry.id)
            path = f"boards/{entry.id}-{paths.slug(record['content'])}.json"
            archive.writestr(path, json.dumps(record, ensure_ascii=False, indent=1))
            boards.append({"id": entry.id, "file": path})
        else:
            row, lost = _write_note(archive, record, uploads_dir, stored)
            notes.append(row)
            missing.extend(lost)
        if progress is not None:
            progress(done, len(entries))
    documents = _write_documents(archive, session, related)
    manifest = {
        "format": FORMAT, "version": VERSION, "app_version": __version__,
        "exported_at": datetime.now().astimezone().isoformat(),
        "counts": {"notes": len(notes), "boards": len(boards), "documents": len(documents),
                   "attachments": sum(len(n["attachments"]) for n in notes), "missing": len(missing)},
        "categories": _categories(session),
        "notes": notes, "boards": boards, "documents": documents, "missing": missing,
    }
    archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=1))
    return ExportResult(manifest=manifest, missing=missing, seconds=time.perf_counter() - t0)


# --- the folder back in: the "memorymap" source of `app_import.read` ---------------

#: One attachment may be as large as an upload is (`routes_files.MAX_FILE_BYTES`).
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024


def _decoded(data: bytes) -> str | None:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _json(data: bytes) -> dict | None:
    text = _decoded(data)
    try:
        value = json.loads(text) if text is not None else None
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _prefix(names: list[str]) -> str:
    """The folder the export sits in inside the zip ("" or "name/"): where
    `index.json` is, else where `notes/` starts."""
    for name in names:
        if posixpath.basename(name) == MANIFEST:
            return name[: -len(MANIFEST)]
    for name in names:
        at = name.find("notes/")
        if at == 0 or (at > 0 and name[at - 1] == "/"):
            return name[:at]
    return ""


def _strip_attachments(body: str) -> str:
    at = body.find(ATTACHMENTS_MARK)
    return body[:at].rstrip() if at >= 0 else body


@dataclass
class _Parts:
    """One note's (or document's) files, by the path without its suffix."""

    md: bytes | None = None
    sidecar: bytes | None = None
    files: dict = field(default_factory=dict)


def _place(rel: str, data: bytes, bases: set[str], groups: dict) -> bool:
    """File one member under its note, document or board. False when it is
    none of them."""
    base, ext = posixpath.splitext(rel)
    if rel.startswith("boards/") and ext == ".json":
        groups["boards"][base] = data
    elif rel.startswith("notes/") and posixpath.dirname(rel) in bases:
        #: Before the note test: an attached `.json` or `.md` is a file.
        groups["notes"].setdefault(posixpath.dirname(rel), _Parts()).files[posixpath.basename(rel)] = data
    elif rel.startswith(("notes/", "documents/")) and ext in (".md", ".json"):
        parts = groups["notes" if rel.startswith("notes/") else "documents"].setdefault(base, _Parts())
        setattr(parts, "md" if ext == ".md" else "sidecar", data)
    else:
        return False
    return True


def _group(files: list[tuple[str, bytes]], prefix: str, skipped: list[str]) -> tuple[dict, dict | None]:
    """The notes', documents' and boards' parts, and the manifest."""
    groups: dict = {"notes": {}, "documents": {}, "boards": {}}
    manifest = None
    inside = [(name[len(prefix):], name, data) for name, data in files if name.startswith(prefix)]
    bases = {posixpath.splitext(rel)[0] for rel, _, _ in inside if rel.endswith((".md", ".json"))}
    for name, _ in files:
        if not name.startswith(prefix):
            skipped.append(f"{name}: outside the exported folder")
    for rel, name, data in inside:
        if rel == MANIFEST:
            manifest = _json(data)
            if manifest is None or manifest.get("format") != FORMAT:
                skipped.append(f"{name}: not a Tessellate folder manifest")
                manifest = None
        elif not _place(rel, data, bases, groups):
            skipped.append(f"{name}: not part of a Tessellate folder export")
    return groups, manifest


def _from_markdown(text: str, parse_frontmatter) -> dict:  # noqa: ANN001
    """A note written into the folder by hand, with no sidecar: what its front
    matter says, the rest at the defaults."""
    meta, body = parse_frontmatter(text) if parse_frontmatter else ({}, text)
    created = meta.get("created")
    return {"content": _strip_attachments(body).strip(), "sealed": False, "category": meta.get("category"),
            "tags": list(meta.get("tags") or []), "pinned": bool(meta.get("pinned")),
            "created_at": created.isoformat() if isinstance(created, datetime) else None,
            "attachments": [], "links": [], "reminders": []}


def _note_record(base: str, parts: _Parts, parse_frontmatter, skipped: list[str]) -> dict | None:  # noqa: ANN001
    """The sidecar when it reads; the markdown when it does not."""
    record = _json(parts.sidecar) if parts.sidecar is not None else None
    if record is not None and isinstance(record.get("content"), str):
        return record
    if parts.sidecar is not None:
        skipped.append(f"{base}.json: the sidecar could not be read" + (", so the note was read from its markdown" if parts.md else ""))
    text = _decoded(parts.md) if parts.md is not None else None
    if parts.md is not None and text is None:
        skipped.append(f"{base}.md: not a text file")
        return None
    if text is None:
        if parts.sidecar is None:
            skipped.append(f"{base}: attachments with no note beside them")
        return None
    record = _from_markdown(text, parse_frontmatter)
    if not record["content"]:
        skipped.append(f"{base}.md: empty")
        return None
    record["attachments"] = [{"file": name, "filename": name} for name in sorted(parts.files)]
    return record


def _imported(base: str, record: dict, parts: _Parts, skipped: list[str]) -> dict:
    """One note as `app_import.Imported`'s fields (built there: this module
    is imported by that one, never the other way)."""
    files = {}
    for attachment in record.get("attachments") or []:
        data = parts.files.get(attachment.get("file"))
        if data is None:
            skipped.append(f"{base}/{attachment.get('file')}: attachment missing from the folder")
        elif len(data) > MAX_ATTACHMENT_BYTES:
            skipped.append(f"{base}/{attachment.get('file')}: larger than 50 MB")
        else:
            files[attachment["file"]] = data
    created = _parsed("created_at", record.get("created_at"))
    if isinstance(created, datetime) and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)  # the database's own reading of a naive stamp
    return {"key": str(record.get("id") or base), "title": posixpath.basename(base), "body": record["content"],
            "tags": list(record.get("tags") or []), "category": record.get("category"), "created": created,
            "path": base, "record": record, "files": files}


def _documents_in(documents: dict, skipped: list[str]) -> list[dict]:
    out = []
    for base in sorted(documents):
        record = _json(documents[base].sidecar) if documents[base].sidecar else None
        text = _decoded(documents[base].md) if documents[base].md is not None else None
        if record is None and text is None:
            skipped.append(f"{base}: the document could not be read")
            continue
        out.append(record or {"title": posixpath.basename(base), "content": text, "file_type": "md"})
    return out


def read(files: list[tuple[str, bytes]], parse_frontmatter=None) -> tuple[list[dict], list[str], dict]:  # noqa: ANN001
    """The folder an export wrote: notes and boards as `Imported` fields
    with their sidecar in `record`, what was left out and why, and the
    documents and the manifest's categories."""
    skipped: list[str] = []
    notes: list[dict] = []
    groups, manifest = _group(files, _prefix([name for name, _ in files]), skipped)
    for base in sorted(groups["notes"]):
        record = _note_record(base, groups["notes"][base], parse_frontmatter, skipped)
        if record is not None:
            notes.append(_imported(base, record, groups["notes"][base], skipped))
    for base in sorted(groups["boards"]):
        record = _json(groups["boards"][base])
        if record is None or not isinstance(record.get("content"), str):
            skipped.append(f"{base}.json: the board could not be read")
            continue
        notes.append(_imported(base, record, _Parts(), skipped))
    extra = {"documents": _documents_in(groups["documents"], skipped),
             "categories": (manifest or {}).get("categories") or []}
    return notes, skipped, extra


# --- the writer -------------------------------------------------------------------


def _fingerprint(created: object, content: str) -> tuple:
    stamp = created.isoformat() if isinstance(created, datetime) else str(created or "")
    return stamp, hashlib.sha1((content or "").encode()).hexdigest()  # noqa: S324


def _existing_notes(session, notes: list) -> dict:  # noqa: ANN001
    """Fingerprints of the notes already here, for the import's "already
    here": the same day and the same text is the same note."""
    from sqlalchemy import select

    from tessellate.core.database import Entry

    days = sorted({n.created for n in notes if n.created is not None})
    found: dict = {}
    for at in range(0, len(days), 500):
        for entry in session.scalars(select(Entry).where(Entry.created_at.in_(days[at:at + 500]))):
            found[_fingerprint(entry.created_at, entry.content)] = entry.id
            found.setdefault(_fingerprint(entry.created_at, _readable(entry)[0]), entry.id)
    return found


#: Columns `_make_entry` sets itself, or the second pass does.
_ENTRY_SKIP = set(ENTRY_LEFT_OUT) | {"parent_id", "is_private"}


def _make_entry(session, record: dict, said: list[str]):  # noqa: ANN001, ANN202
    from tessellate.core import vault
    from tessellate.entry import manager
    from tessellate.entry import manager_private

    entry = manager.create_entry(session, record["content"], category_name=record.get("category") or manager.UNCATEGORISED,
                                 tags=record.get("tags") or [], ai_confidence=int(record.get("ai_confidence") or 0), commit=False,
                                 dates=not record.get("created_at"))
    _restore(entry, record, _ENTRY_SKIP)
    _fresh_bin_period(entry)
    if record.get("sealed"):
        entry.is_private = True
    elif record.get("is_private") and vault.key() is not None:
        #: Locked, a readable private note never gets here: `import_app` refuses first (sm-1111 row 8).
        manager_private.set_private(session, entry, True)
    if entry.created_at is not None:
        manager.record_dates(session, entry)
    return entry


def _fresh_bin_period(entry) -> None:  # noqa: ANN001
    """A binned note that came in already past the bin's days would be purged
    at the next start, so an import would lose what it just made: it gets a
    full period from now instead. `_restore` already restarts every stamp, so this
    is the guard for a record whose `deleted_at` was missing or unreadable."""
    if not entry.is_deleted:
        return
    from tessellate.core import deps
    from tessellate.entry import manager

    days = int(deps.get_config().get_preference("recycle_bin_days", 30))
    now = manager.utcnow()
    binned = entry.deleted_at
    if binned is not None and binned.tzinfo is None:
        binned = binned.replace(tzinfo=timezone.utc)
    if binned is None or binned < now - timedelta(days=days):
        entry.deleted_at = now


def _write_attachments(session, entry, note, uploads_dir: Path) -> None:  # noqa: ANN001
    import uuid

    from tessellate.core.database import Attachment

    uploads_dir.mkdir(parents=True, exist_ok=True)
    for record in note.record.get("attachments") or []:
        data = note.files.get(record.get("file"))
        if data is None:
            continue
        stored = f"{uuid.uuid4().hex}{posixpath.splitext(record['file'])[1][:12].lower()}"
        (uploads_dir / stored).write_bytes(data)
        attachment = Attachment(entry_id=entry.id, filename=record.get("filename") or record["file"], stored_name=stored, size=len(data))
        _restore(attachment, record, _ROW_LEFT_OUT | {"entry_id", "stored_name", "size", "file", "sha1"})
        session.add(attachment)


def _hang_links(session, entry, record: dict, idmap: dict, said: list[str]) -> None:  # noqa: ANN001
    from tessellate.core.database import EntryLink, Reminder

    for link in record.get("links") or []:
        target = idmap.get(link.get("target_entry_id"))
        if target is None:
            said.append(f"{record.get('id')}: a link to note {link.get('target_entry_id')}, which is not in the folder")
            continue
        row = EntryLink(source_entry_id=entry.id, target_entry_id=target)
        _restore(row, link, _ROW_LEFT_OUT | {"source_entry_id", "target_entry_id"})
        session.add(row)
    for reminder in record.get("reminders") or []:
        row = Reminder(entry_id=entry.id, text=reminder.get("text") or "", due_at=_parsed("due_at", reminder.get("due_at")))
        _restore(row, reminder, _ROW_LEFT_OUT | {"entry_id", "document_id"})
        session.add(row)


def _hang_canvas(session, board, canvas: dict, idmap: dict, said: list[str]) -> None:  # noqa: ANN001
    from tessellate.core.database import WhiteboardNode, WhiteboardObject, WhiteboardSketch

    #: Each list kept in step with the export's, a skipped card as None, so a
    #: connector's end by place (`_link_ends`) finds the row that took it.
    cards = _hang_cards(session, board, canvas, idmap, said, WhiteboardNode)
    lines = _hang_rows(session, WhiteboardSketch, board, canvas.get("sketches"), _ROW_LEFT_OUT | {"board_id"})
    shapes = _hang_rows(session, WhiteboardObject, board, canvas.get("objects"), _ROW_LEFT_OUT | {"board_id", "parent_id"})
    session.flush()
    for row, shape in zip(shapes, canvas.get("objects") or []):
        _fix_object_links(row, shape, shapes, board, idmap, said)
    rows = {"node": cards, "object": shapes, "sketch": lines}
    for row, sketch in zip(lines, canvas.get("sketches") or []):
        _hang_connector_ends(row, sketch, rows, board, said)


def _hang_cards(session, board, canvas: dict, idmap: dict, said: list[str], model) -> list:  # noqa: ANN001
    cards = []
    for node in canvas.get("nodes") or []:
        target = idmap.get(node.get("entry_id"))
        if target is None:
            said.append(f"board {board.id}: a card for note {node.get('entry_id')}, which is not in the folder")
            cards.append(None)
            continue
        row = model(board_id=board.id, entry_id=target)
        _restore(row, node, _ROW_LEFT_OUT | {"board_id", "entry_id"})
        session.add(row)
        cards.append(row)
    return cards


def _hang_rows(session, model, board, items, left_out) -> list:  # noqa: ANN001
    """One new row of `model` per exported item, on this board."""
    rows = []
    for item in items or []:
        row = model(board_id=board.id)
        _restore(row, item, left_out)
        session.add(row)
        rows.append(row)
    return rows


def _fix_object_links(row, shape: dict, shapes: list, board, idmap: dict, said: list[str]) -> None:  # noqa: ANN001
    """Point an object at its new parent row, and a map's note reference at the new note id."""
    place = shape.get("parent_id")
    changed = False
    if isinstance(place, int) and 0 <= place < len(shapes):
        row.parent_id = shapes[place].id
        changed = True
    #: A map's note reference names a note by id, which is new here too.
    data = _json_dict(row.data)
    if row.kind == "note" and isinstance(data.get("ref_id"), int):
        new = idmap.get(data["ref_id"])
        if new is None:
            said.append(f"board {board.id}: a map node for note {data['ref_id']}, which is not in the folder")
        elif new != data["ref_id"]:
            row.data = json.dumps(dict(data, ref_id=new))
            changed = True
    if changed:
        _keep_updated(row, shape)


def _hang_connector_ends(row, sketch: dict, rows: dict, board, said: list[str]) -> None:  # noqa: ANN001
    """Rewrite a connector's source and target ids to the rows that took their place."""
    ends = sketch.get("ends")
    if not isinstance(ends, dict):
        return
    data = _json_dict(row.data)
    for side, end in ends.items():
        if side not in ("source", "target") or not isinstance(end, list) or len(end) != 2:
            continue
        kind, at = end
        found = rows.get(kind, [])
        item = found[at] if isinstance(at, int) and 0 <= at < len(found) else None
        if item is None:
            said.append(f"board {board.id}: a connector's {side} end, whose item is not in the folder")
            continue
        data[f"{side}Id"] = item.id
    row.data = json.dumps(data)
    _keep_updated(row, sketch)


def _json_dict(text: str | None) -> dict:
    try:
        parsed = json.loads(text or "")
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _keep_updated(row, record: dict) -> None:  # noqa: ANN001
    """A second write to a row is an UPDATE, and `updated_at` has an
    `onupdate` that fires unless the column is in the statement. Setting it
    to the value it already holds is no change to SQLAlchemy, so it is
    marked modified by hand and the row keeps the day it carried."""
    from sqlalchemy.orm.attributes import flag_modified

    value = _parsed("updated_at", record.get("updated_at"))
    if value is not None:
        row.updated_at = value
        flag_modified(row, "updated_at")


def _second_pass(session, made: list, idmap: dict, said: list[str]) -> None:  # noqa: ANN001
    """What points at other notes, once every note has its new id."""
    for entry, record in made:
        parent = record.get("parent_id")
        if parent is not None:
            entry.parent_id = idmap.get(parent)
        _hang_links(session, entry, record, idmap, said)
        if record.get("canvas"):
            _hang_canvas(session, entry, record["canvas"], idmap, said)
        _keep_updated(entry, record)


def _existing_documents(session) -> set:  # noqa: ANN001
    from sqlalchemy import select

    from tessellate.core.database import Document
    from tessellate.entry.bin import including_binned

    #: The bin too: the export carries binned documents, so a re-import merges them.
    with including_binned(session):
        return {(_fingerprint(d.created_at, d.content), d.title) for d in session.scalars(select(Document))}


def _write_documents_in(session, records: list[dict], idmap: dict, said: list[str]) -> tuple[int, int]:  # noqa: ANN001
    from tessellate.core.database import Document, DocumentLink, Reminder

    existing = _existing_documents(session)
    written = merged = 0
    for record in records:
        key = (_fingerprint(_parsed("created_at", record.get("created_at")), record.get("content") or ""), record.get("title"))
        if key in existing:
            merged += 1
            continue
        document = Document()
        _restore(document, record, _ROW_LEFT_OUT)
        session.add(document)
        session.flush()
        written += 1
        for entry_id in record.get("notes") or []:
            if idmap.get(entry_id) is None:
                said.append(f"document {record.get('title')}: a note {entry_id} not in the folder")
                continue
            session.add(DocumentLink(document_id=document.id, entry_id=idmap[entry_id]))
        for reminder in record.get("reminders") or []:
            row = Reminder(document_id=document.id, text=reminder.get("text") or "", due_at=_parsed("due_at", reminder.get("due_at")))
            _restore(row, reminder, _ROW_LEFT_OUT | {"entry_id", "document_id"})
            session.add(row)
    return written, merged


def _categories_in(session, categories: list[dict]) -> None:  # noqa: ANN001
    from tessellate.entry import manager

    for row in categories:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        category = manager.get_or_create_category(session, row["name"])
        category.colour = category.colour or row.get("colour")
        category.description = category.description or row.get("description")


@dataclass
class Progress:
    """What the writer reports as it goes, and how it is told to stop."""

    stopped: object = None  # () -> bool
    step: object = None  # (done, total) -> None
    every: int = 100


def write(session, result, uploads_dir: Path, progress: Progress | None = None) -> dict:  # noqa: ANN001
    """Make the notes, boards and documents not already here. Returns the
    counts, the ids made, the old-to-new id map, and lines worth saying."""
    progress = progress or Progress()
    _categories_in(session, result.extra.get("categories") or [])
    existing = _existing_notes(session, result.notes)
    idmap: dict = {}
    made: list = []
    said: list[str] = []
    merged = 0
    stopped = False
    for done, note in enumerate(result.notes, 1):
        if progress.stopped is not None and progress.stopped():
            stopped = True
            break
        old = note.record.get("id")
        found = existing.get(_fingerprint(note.created, note.body))
        if found is not None:
            idmap[old] = found
            merged += 1
        else:
            entry = _make_entry(session, note.record, said)
            idmap[old] = entry.id
            _write_attachments(session, entry, note, uploads_dir)
            made.append((entry, note.record))
            if done % progress.every == 0:
                session.commit()
        if progress.step is not None and (done % progress.every == 0 or done == len(result.notes)):
            progress.step(done, len(result.notes))
    _second_pass(session, made, idmap, said)
    documents = (0, 0) if stopped else _write_documents_in(session, result.extra.get("documents") or [], idmap, said)
    session.commit()
    return {"imported": len(made), "already": merged, "ids": [e.id for e, _ in made], "entries": [e for e, _ in made],
            "idmap": idmap, "said": said, "stopped": stopped, "documents": documents[0], "documents_already": documents[1],
            "people": [], "places": []}
