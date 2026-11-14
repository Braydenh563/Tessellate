"""Documents, boards and attached files between paired computers (WORLD_CLASS_PLAN B6, decision 13).

Notes travel by the audit log (decision 1). These three do not all reach it
(a document's edit, a card moved on a board, a drawing removed), so they
travel by state: after the notes, the puller reads the other computer's
manifest, one line per item with a hash of its portable state (every id
that differs between the two computers replaced by a sid), and fetches only
the items whose hash differs from its own copy's. Applying them is
`sync_extras_apply.py`.

A private document or board ships its sealed columns as the ciphertext they
hold (read past the column type, which answers a pass with the locked
placeholder) and is opened with both keys on the other side, as a private
note is (decision 12). Its hash is its time and its row counts, since the
two computers' ciphertexts of the same words differ. An item a private space
seals is listed with an empty hash: it exists, and it stays home.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import Text, select, type_coerce
from sqlalchemy.orm import Session

from tessellate.core import sync_state
from tessellate.core.database import (
    Attachment,
    Document,
    DocumentLink,
    Entry,
    WhiteboardNode,
    WhiteboardObject,
    WhiteboardSketch,
    impersonate_workspace,
)
from tessellate.entry import export_folder
from tessellate.entry.sync_segments import note_sid

FORMAT = 1
#: Items per `items` answer; the puller asks in turns.
MAX_ITEMS = 50
KINDS = ("document", "board", "file")
#: A board's rows, in the order the export folder writes them.
CANVAS = (("nodes", WhiteboardNode), ("sketches", WhiteboardSketch), ("objects", WhiteboardObject))
#: The columns a private owner seals (as `database._SEALED_COLUMNS` has them).
SEALED = {Document: ("title", "content", "threads"), WhiteboardSketch: ("data",), WhiteboardObject: ("data",)}
_ROW_LEFT_OUT = {"workspace_id", "board_id", "created_at"}


#: The manifest hash of a document or board the folder withdraws (INBOX 1783): it matches no real hash.
WITHHELD = "withheld"


def withheld(state: dict) -> dict[str, Any]:
    """A document or board made private after it went out in the clear: its name and time only."""
    return {"kind": state["kind"], "sid": state["sid"], "is_private": True, "withheld": True,
            "updated_at": state["updated_at"]}


def iso(value: Any) -> str | None:
    return export_folder._iso(value) if value is not None else None  # noqa: SLF001  # one date format for both


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class Names:
    """This notebook's sids: an item that came from another computer keeps the sid it came with."""

    def __init__(self, session: Session, device: str, landed: dict[str, dict[str, list]]) -> None:
        self.session, self.device = session, device
        self.arrived = {kind: {sid: local for sid, (local, stamp) in rows.items() if _still(session, kind, local, stamp)}
                        for kind, rows in landed.items()}
        self._back = {kind: {i: s for s, i in rows.items()} for kind, rows in self.arrived.items()}

    def of(self, kind: str, local_id: int) -> str:
        return self._back.get(kind, {}).get(local_id) or f"{self.device}:{local_id}"

    def note(self, entry_id: int | None) -> str | None:
        entry = self.session.get(Entry, entry_id) if entry_id is not None else None
        return note_sid(entry, self.device) if entry is not None else None

    def local(self, kind: str, sid: str) -> int | None:
        """The local id of `sid`, if it is here."""
        device, _, number = sid.partition(":")
        if device == self.device:
            return int(number) if number.isdigit() else None
        return self.arrived.get(kind, {}).get(sid)


def mark(row: Document | Attachment) -> str:
    """What tells a row that came from another computer from a later one given its freed id."""
    return row.stored_name if isinstance(row, Attachment) else iso(row.created_at) or ""


def _still(session: Session, kind: str, local: int, stamp: str) -> bool:
    row = session.get(Attachment if kind == "file" else Document, local)
    return row is not None and (not stamp or mark(row) == stamp)


def raw(session: Session, model: type, row_id: int) -> dict[str, str]:
    """A private row's sealed columns as stored: ciphertext, whoever is asking."""
    columns = [type_coerce(getattr(model, name), Text).label(name) for name in SEALED[model]]
    found = session.execute(select(*columns).where(model.id == row_id)).one()
    return {name: found._mapping[name] or "" for name in SEALED[model]}


def document_state(session: Session, doc: Document, names: Names) -> dict[str, Any]:
    words = raw(session, Document, doc.id) if doc.is_private else {
        "title": doc.title, "content": doc.content, "threads": doc.threads or ""}
    linked = session.scalars(select(DocumentLink.entry_id).where(DocumentLink.document_id == doc.id))
    state = {"kind": "document", "sid": names.of("document", doc.id), **words, "file_type": doc.file_type,
             "space": doc.workspace_id or "default", "is_private": bool(doc.is_private),
             "archived_at": iso(doc.archived_at), "deleted_at": iso(doc.deleted_at),
             "notes": sorted({s for s in map(names.note, linked) if s}), "updated_at": iso(doc.updated_at) or ""}
    if doc.parent_id is not None:  # a sub-page names its parent by sid; absent on a top-level page, so old hashes hold
        state["parent"] = names.of("document", doc.parent_id)
    return state


def _canvas(session: Session, board: Entry) -> dict[str, list[dict]]:
    """The board's rows with this notebook's ids, a private board's sealed columns as stored."""
    out = {}
    for key, model in CANVAS:
        rows = []
        for row in session.scalars(select(model).where(model.board_id == board.id).order_by(model.id)):
            record = export_folder._row(row, _ROW_LEFT_OUT)  # noqa: SLF001  # the export's one row shape
            if board.is_private and model in SEALED:
                record.update(raw(session, model, row.id))
            rows.append(record)
        out[key] = rows
    return out


def _stamp(board: Entry, canvas: dict) -> str:
    """A board's time: the latest of the board's and every row's."""
    times = [iso(board.updated_at) or ""] + [r.get("updated_at") or "" for rows in canvas.values() for r in rows]
    return max(times)


def board_state(session: Session, board: Entry, names: Names) -> dict[str, Any]:
    canvas = _canvas(session, board)
    refs = {str(n["entry_id"]): names.note(n["entry_id"]) for n in canvas["nodes"]}
    for shape in canvas["objects"]:
        ref = _json(shape.get("data")).get("ref_id")
        if isinstance(ref, int):
            refs[str(ref)] = names.note(ref)
    return {"kind": "board", "sid": note_sid(board, names.device), "content": board.content,
            "board_settings": board.board_settings, "space": board.workspace_id or "default",
            "is_private": bool(board.is_private), "is_deleted": bool(board.is_deleted),
            "deleted_at": iso(board.deleted_at), "archived_at": iso(board.archived_at),
            "canvas": canvas, "refs": {k: v for k, v in refs.items() if v}, "updated_at": _stamp(board, canvas)}


def _json(text: object) -> dict:
    try:
        found = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        return {}
    return found if isinstance(found, dict) else {}


def folder_canvas(canvas: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """The export folder's canvas shape: no ids, a parent and a connector's ends named by place,
    so `export_folder._hang_canvas` can hang it here."""
    places = {kind: {row["id"]: i for i, row in enumerate(canvas.get(key) or [])}
              for kind, key in (("node", "nodes"), ("sketch", "sketches"), ("object", "objects"))}
    nodes = [_no_id(row) for row in canvas.get("nodes") or []]
    shapes = [_no_id(row) | {"parent_id": places["object"].get(row.get("parent_id"))} for row in canvas.get("objects") or []]
    return {"nodes": nodes, "sketches": [_line(row, places) for row in canvas.get("sketches") or []], "objects": shapes}


def _no_id(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "id"}


def _line(row: dict, places: dict) -> dict:
    record = _no_id(row)
    ends = export_folder._link_ends(row.get("data"), places)  # noqa: SLF001  # the export's connector ends
    if ends:
        record["ends"] = ends
    return record


def _portable_board(state: dict) -> dict:
    """What a board's hash covers: its canvas by place and by note sid, no ids and no times."""
    refs = state["refs"]
    canvas = folder_canvas(state["canvas"])
    for row in canvas["nodes"]:
        row["entry_id"] = refs.get(str(row.get("entry_id")))
    for row in canvas["objects"]:
        data = _json(row.get("data"))
        if isinstance(data.get("ref_id"), int):
            row["data"] = json.dumps(dict(data, ref_id=refs.get(str(data["ref_id"]))), sort_keys=True)
    for row in canvas["sketches"]:
        data = _json(row.get("data"))
        if row.get("ends") and data:
            row["data"] = json.dumps({k: v for k, v in data.items() if k not in ("sourceId", "targetId")}, sort_keys=True)
    for rows in canvas.values():
        for row in rows:
            row.pop("updated_at", None)
    return {k: v for k, v in state.items() if k not in ("canvas", "refs", "updated_at")} | {"canvas": canvas}


def item_hash(state: dict) -> str:
    """Equal on both computers exactly when the item is the same there."""
    if state.get("is_private"):
        counts = {k: len(v) for k, v in (state.get("canvas") or {}).items()}
        return digest([state["kind"], state["sid"], state["updated_at"], state.get("deleted_at"),
                       state.get("archived_at"), counts])
    if state["kind"] == "board":
        return digest(_portable_board(state))
    return digest({k: v for k, v in state.items() if k not in ("updated_at", "created_at", "size")})


#: SHA-1 of an upload by (stored name, size, mtime_ns): a manifest is built for every sync, and the
#: bytes of an unchanged file do not need reading again. Bounded; the oldest entry goes first.
_SHA1_CACHE: OrderedDict[tuple[str, int, int], str] = OrderedDict()
#: Manifests are built on the request threadpool and on the sync thread at once.
_SHA1_LOCK = threading.Lock()
_SHA1_CACHE_MAX = 4096


def _file_sha1(path: Path, stored_name: str) -> str:
    try:
        stat = path.stat()
    except OSError:
        return ""
    if not path.is_file():
        return ""
    key = (stored_name, stat.st_size, stat.st_mtime_ns)
    with _SHA1_LOCK:
        found = _SHA1_CACHE.get(key)
    if found is None:
        found = hashlib.sha1(path.read_bytes(), usedforsecurity=False).hexdigest()
        with _SHA1_LOCK:
            _SHA1_CACHE[key] = found
            while len(_SHA1_CACHE) > _SHA1_CACHE_MAX:
                _SHA1_CACHE.popitem(last=False)
    return found


def file_state(att: Attachment, names: Names, uploads: Path) -> dict[str, Any]:
    sha1 = _file_sha1(uploads / att.stored_name, att.stored_name)
    return {"kind": "file", "sid": names.of("file", att.id), "note": names.note(att.entry_id),
            "filename": att.filename, "mime": att.mime, "size": att.size, "sha1": sha1,
            "created_at": iso(att.created_at)}


def _rows(session: Session, names: Names, uploads: Path) -> Iterator[tuple[dict | None, str, str]]:
    """(state or None when a private space keeps it home, kind, sid) for every item."""
    for doc in session.scalars(select(Document).order_by(Document.id)):
        yield (None if doc.sealed_by_space else document_state(session, doc, names)), "document", names.of("document", doc.id)
    for board in session.scalars(select(Entry).where(Entry.is_board.is_(True)).order_by(Entry.id)):
        yield (None if board.sealed_by_space else board_state(session, board, names)), "board", note_sid(board, names.device)
    # One query for every file and its note; the notes land in the session, so `names.note` finds them there.
    for att, note in session.execute(select(Attachment, Entry).join(Entry, Entry.id == Attachment.entry_id, isouter=True)
                                     .order_by(Attachment.id)).all():
        kept = note is None or note.sealed_by_space
        yield (None if kept else file_state(att, names, uploads)), "file", names.of("file", att.id)


def names_for(session: Session, data_dir: Path, device: str) -> Names:
    return Names(session, device, sync_state.arrived(data_dir))


def manifest(session: Session, data_dir: Path, device: str) -> dict[str, Any]:
    """One line per document, board and file: kind, sid and the hash of its state."""
    names = names_for(session, data_dir, device)
    with impersonate_workspace(session, ""):
        lines = [{"kind": kind, "sid": sid, "hash": item_hash(state) if state else ""}
                 for state, kind, sid in _rows(session, names, data_dir / "uploads")]
    return {"format": FORMAT, "device": device, "items": lines, "digest": digest(lines)}


def _find_row(session: Session, names: Names, kind: str, sid: str) -> Any:
    if kind == "board":
        from tessellate.entry.sync_segments import _find  # noqa: PLC0415  # the note lookup, one place

        found = _find(session, names.device, sid)
        return found if found is not None and found.is_board else None
    local = names.local(kind, sid)
    return session.get(Document if kind == "document" else Attachment, local) if local is not None else None


def items(session: Session, data_dir: Path, device: str, kind: str, sids: list[str]) -> list[dict[str, Any]]:
    """The whole state of each asked item that is here and may leave."""
    names = names_for(session, data_dir, device)
    out = []
    with impersonate_workspace(session, ""):
        for sid in sids[:MAX_ITEMS]:
            row = _find_row(session, names, kind, sid)
            state = _state(session, names, kind, row, data_dir / "uploads") if row is not None else None
            if state is not None:
                out.append(state)
    return out


def _state(session: Session, names: Names, kind: str, row: Any, uploads: Path) -> dict | None:
    if kind == "file":
        note = session.get(Entry, row.entry_id)
        return file_state(row, names, uploads) if note is not None and not note.sealed_by_space else None
    if row.sealed_by_space:
        return None
    return document_state(session, row, names) if kind == "document" else board_state(session, row, names)


def file_bytes(session: Session, data_dir: Path, device: str, sid: str) -> tuple[bytes, str] | None:
    """An attached file's bytes and type, if it is here and may leave."""
    names = names_for(session, data_dir, device)
    with impersonate_workspace(session, ""):
        att = _find_row(session, names, "file", sid)
        if att is None or _state(session, names, "file", att, data_dir / "uploads") is None:
            return None
        path = data_dir / "uploads" / att.stored_name
        return (path.read_bytes(), att.mime) if path.is_file() else None
