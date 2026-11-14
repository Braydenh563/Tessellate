"""Documents, boards and attached files into this notebook (WORLD_CLASS_PLAN B6, decision 13).

After the notes, `pull_extras` reads the other computer's manifest
(`sync_extras.manifest`), asks for the items whose hash differs from this
notebook's copy, and applies each with the notes' rule: the later
`updated_at` wins the whole item, on a tie the larger device id, and a
document's words that lose are kept as a version in its History. Each item
commits on its own, so a pull cut off part way is simply run again.

A file is fetched once, checked against its SHA-1, and never changes after;
one removed on the other computer is removed here when it came from there
or the other computer had listed it before. A private document or board
opens only with both keys (decision 12); without them it waits, and the
Settings line says private items stay unreadable.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from tessellate.core import crypto, events, sync_state
from tessellate.core.database import Attachment, AuditLog, Document, DocumentLink, DocumentRevision, Entry, Space, impersonate_workspace
from tessellate.entry import export_folder, manager, sync_extras, sync_keys
from tessellate.entry.bin import purge_document
from tessellate.repo import documents as document_repo
from tessellate.entry.sync_segments import DAMAGED, KEY_PREFIX, SegmentError, _find, withdraw, withdraw_verdict

#: How many files one pull fetches at most; the rest come at the next.
MAX_FILES = 200


def _when(text: object) -> datetime | None:
    """A stamp as naive UTC, the way the columns hold it."""
    try:
        found = datetime.fromisoformat(text) if isinstance(text, str) and text else None
    except ValueError:
        return None
    return found.astimezone(timezone.utc).replace(tzinfo=None) if found and found.tzinfo else found


#: `<device>:<local id>` (sync_extras.Names.of): letters, digits, `_` and `-` only. A sid becomes a file name in a
#: sync folder (folder_sync._blob_name), so a peer's sid with a separator or `..` is refused with its manifest.
_SID = re.compile(r"[A-Za-z0-9]{1,64}:[A-Za-z0-9_-]{1,64}")


def checked(answer: object, peer: str) -> list[dict]:
    """The manifest's lines, or SegmentError before anything is fetched."""
    if not isinstance(answer, dict) or answer.get("format") != sync_extras.FORMAT or answer.get("device") != peer:
        raise SegmentError(DAMAGED)
    lines = answer.get("items")
    if not isinstance(lines, list) or answer.get("digest") != sync_extras.digest(lines):
        raise SegmentError(DAMAGED)
    if not all(isinstance(x, dict) and x.get("kind") in sync_extras.KINDS and isinstance(x.get("sid"), str)
               and _SID.fullmatch(x["sid"]) and isinstance(x.get("hash"), str) for x in lines):
        raise SegmentError(DAMAGED)
    return lines


def _theirs_win(mine: datetime | None, item: dict, me: str, peer: str) -> bool:
    theirs = _when(item.get("updated_at"))
    if theirs is None:
        return False
    if mine is not None and mine.tzinfo is not None:  # a row written this session, not yet read back
        mine = mine.astimezone(timezone.utc).replace(tzinfo=None)
    return mine is None or theirs > mine or (theirs == mine and peer > me)


def _opened(value: str, both: sync_keys.Keys | None) -> str | None:
    """A sealed value from the other computer sealed again with this one's key; None without both keys."""
    if not value or not crypto.is_encrypted(value):
        return value
    if both is None:
        return None
    try:
        return crypto.encrypt(both[1], crypto.decrypt(both[0], value))
    except crypto.DecryptionError:
        return None


def _plain(value: str, key: bytes) -> str | None:
    try:
        return crypto.decrypt(key, value) if value and crypto.is_encrypted(value) else value
    except crypto.DecryptionError:
        return None


def _space(session: Session, space: object) -> str:
    return space if isinstance(space, str) and session.get(Space, space) is not None else "default"


class Apply:
    """One pull's items into this notebook."""

    def __init__(self, session: Session, data_dir: Path, me: str, peer: str, both: sync_keys.Keys | None) -> None:
        self.session, self.data_dir, self.me, self.peer, self.both = session, data_dir, me, peer, both
        self.names = sync_extras.names_for(session, data_dir, me)
        #: Items changed only on the other computer since the last sync: theirs, whatever the times.
        self.force: set[str] = set()
        #: Removal marks held until `flush`: one write of sync-state per page. A removal mark lost to a
        #: crash is safe (the file is already gone and is removed again). A mark for a created row is NOT
        #: batched: it is written before the commit, because a committed row with no mark is published
        #: as this computer's own and fetched back as a duplicate.
        self.marks: list[tuple[str, str, int | None, str]] = []
        #: (document id, the parent's sid) for each document written this pull: the parent may land after its
        #: child, so the links are made once every document is in (`link_parents`).
        self.parents: list[tuple[int, str | None]] = []

    def link_parents(self) -> None:
        """Sub-pages put under their parents by sid. A parent that is not here, or a loop, leaves the page where it was."""
        pending, self.parents = self.parents, []
        if not pending:
            return
        self.names = sync_extras.names_for(self.session, self.data_dir, self.me)
        for doc_id, sid in pending:
            doc = self.session.get(Document, doc_id)
            if doc is None:
                continue
            if sid is None:
                doc.parent_id = None
                continue
            local = self.names.local("document", sid)
            parent = self.session.get(Document, local) if local is not None else None
            if parent is not None and not document_repo.would_cycle(self.session, doc.id, parent.id):
                doc.parent_id = parent.id
        self.session.commit()

    def flush(self) -> None:
        marks, self.marks = self.marks, []
        sync_state.save_arrived_many(self.data_dir, marks)

    def _note_id(self, sid: object) -> int | None:
        entry = _find(self.session, self.me, sid) if isinstance(sid, str) and ":" in sid else None
        return entry.id if entry is not None else None

    # --- documents -------------------------------------------------------------

    def _mine_stays(self, row: Any, item: dict) -> bool:
        """Changed on both and this copy is the later: it stays."""
        return row is not None and item["sid"] not in self.force and not _theirs_win(row.updated_at, item, self.me, self.peer)

    def _words(self, item: dict) -> dict | None:
        words = {k: item.get(k) or "" for k in ("title", "content", "threads")}
        if not item.get("is_private"):
            return words
        words = {k: _opened(v, self.both) for k, v in words.items()}
        return None if any(v is None for v in words.values()) else words

    def _withdraw_document(self, item: dict) -> str:
        """A document made private on the other computer after it came here in the clear (INBOX 1783): gone with
        its History and the words in its log, unless it was written or changed here, which stays and says so once."""
        local = self.names.local("document", item["sid"])
        doc = self.session.get(Document, local) if local is not None else None
        if doc is None or doc.is_private:
            return "same"
        verdict = withdraw_verdict(self.session, self.me, item["sid"], ("document", doc.id))
        if verdict != "purge":
            return verdict
        self.session.execute(update(AuditLog).where(AuditLog.entity_type == "document", AuditLog.entity_id == doc.id)
                             .values(detail=None, payload={"private": True}))
        purge_document(self.session, doc)
        self.marks.append(("document", item["sid"], None, ""))
        return "applied"

    def document(self, item: dict) -> str:
        if item.get("withheld") is True:
            if item["sid"].partition(":")[0] != self.peer:  # only the author withdraws its own
                return "same"
            return self._withdraw_document(item)
        words = self._words(item)
        if words is None:
            return "waiting"
        local = self.names.local("document", item["sid"])
        doc = self.session.get(Document, local) if local is not None else None
        if self._mine_stays(doc, item):
            self._keep_theirs(doc, words)
            return "conflicts"
        created = doc is None
        if created:
            doc = Document(workspace_id=_space(self.session, item.get("space")))
            self.session.add(doc)
        else:
            self._keep_mine(doc, words)
        self._write_document(doc, item, words)
        if created:
            sync_state.save_arrived(self.data_dir, "document", item["sid"], doc.id, sync_extras.mark(doc))
        manager.log_action(self.session, "created" if created else "edited", "document", doc.id, "from the other computer")
        return "applied"

    def _write_document(self, doc: Document, item: dict, words: dict) -> None:
        doc.is_private = bool(item.get("is_private"))
        title = words["title"] if doc.is_private else words["title"][:200]
        doc.title, doc.content, doc.threads = title or "Untitled", words["content"], words["threads"]
        doc.file_type = str(item.get("file_type") or "md")[:20]
        doc.archived_at, doc.deleted_at = _when(item.get("archived_at")), _when(item.get("deleted_at"))
        self.session.flush()
        parent = item.get("parent")
        self.parents.append((doc.id, parent if isinstance(parent, str) and _SID.fullmatch(parent) else None))
        self._links(doc, item.get("notes"))
        doc.updated_at = _when(item["updated_at"])
        self.session.flush()

    def _keep_mine(self, doc: Document, theirs: dict) -> None:
        """This notebook's words, kept in the document's History before different ones replace them.

        A private document's are kept as stored, sealed with this key already."""
        own = sync_extras.document_state(self.session, doc, self.names)
        key = self.both[1] if self.both else b""
        same = [_plain(own[k], key) if key else own[k] for k in ("title", "content")] == [
            _plain(theirs[k], key) if key else theirs[k] for k in ("title", "content")]
        if not same:
            self.session.add(DocumentRevision(document_id=doc.id, title=own["title"] or "", content=own["content"] or "",
                                              source="edit", name="Before the other computer's version"))

    def _keep_theirs(self, doc: Document, theirs: dict) -> None:
        """Changed on both and this one is later: the other computer's words go in History, not lost."""
        self.session.add(DocumentRevision(document_id=doc.id, title=theirs["title"] or "", content=theirs["content"] or "",
                                          source="edit", name="The other computer's version"))

    def _links(self, doc: Document, sids: object) -> None:
        wanted = {self._note_id(s) for s in sids} - {None} if isinstance(sids, list) else set()
        have = set(self.session.scalars(select(DocumentLink.entry_id).where(DocumentLink.document_id == doc.id)))
        if have - wanted:
            self.session.execute(delete(DocumentLink).where(DocumentLink.document_id == doc.id,
                                                            DocumentLink.entry_id.in_(have - wanted)))
        for entry_id in sorted(wanted - have):
            self.session.add(DocumentLink(document_id=doc.id, entry_id=entry_id))

    # --- boards ----------------------------------------------------------------

    def _board_words(self, item: dict) -> tuple[dict, str] | None:
        canvas = item.get("canvas") if isinstance(item.get("canvas"), dict) else {}
        content = item.get("content") or ""
        if item.get("is_private"):
            canvas, content = self._opened_canvas(canvas), _opened(content, self.both)
        return None if canvas is None or content is None else (canvas, content)

    def board(self, item: dict) -> str:
        if item.get("withheld") is True:
            if item["sid"].partition(":")[0] != self.peer:
                return "same"
            return withdraw(self.session, self.me, item, self.data_dir / "uploads")
        opened = self._board_words(item)
        if opened is None:
            return "waiting"
        board = _find(self.session, self.me, item["sid"])
        if self._mine_stays(board, item):
            return "conflicts"
        created = board is None
        if created:
            board = Entry(content="", client_key=KEY_PREFIX + item["sid"], is_board=True,
                          workspace_id=_space(self.session, item.get("space")))
            self.session.add(board)
            self.session.flush()
        self._write_board(board, item, *opened)
        manager.log_action(self.session, "created" if created else "edited", "entry", board.id, "from the other computer")
        return "applied"

    def _write_board(self, board: Entry, item: dict, canvas: dict, content: str) -> None:
        board.content, board.board_settings = content, item.get("board_settings")
        board.is_private, board.is_deleted = bool(item.get("is_private")), bool(item.get("is_deleted"))
        board.deleted_at, board.archived_at = _when(item.get("deleted_at")), _when(item.get("archived_at"))
        for _, model in reversed(sync_extras.CANVAS):
            self.session.execute(delete(model).where(model.board_id == board.id))
        refs = item.get("refs") if isinstance(item.get("refs"), dict) else {}
        idmap = {int(k): self._note_id(v) for k, v in refs.items() if k.isdigit()}
        export_folder._hang_canvas(self.session, board, sync_extras.folder_canvas(canvas),  # noqa: SLF001
                                   {k: v for k, v in idmap.items() if v is not None}, [])
        self.session.flush()
        board.updated_at = _when(item["updated_at"])
        self.session.flush()

    def _opened_canvas(self, canvas: dict) -> dict | None:
        """A private board's rows in the clear, to hang here (the flush seals them with this key)."""
        if self.both is None:
            return None
        out = {}
        for key, model in sync_extras.CANVAS:
            rows = []
            for row in canvas.get(key) or []:
                opened = {name: _plain(row.get(name) or "", self.both[0]) for name in sync_extras.SEALED.get(model, ())}
                if any(v is None for v in opened.values()):
                    return None
                rows.append({**row, **opened})
            out[key] = rows
        return out

    # --- files -----------------------------------------------------------------

    def file(self, item: dict, data: bytes | None) -> str:
        note = self._note_id(item.get("note"))
        if note is None or data is None:
            return "waiting"
        if hashlib.sha1(data, usedforsecurity=False).hexdigest() != item.get("sha1"):
            raise SegmentError(DAMAGED)
        name = str(item.get("filename") or "file")[:255]
        stored = f"{uuid.uuid4().hex}{Path(name).suffix[:12].lower()}"
        uploads = self.data_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        (uploads / stored).write_bytes(data)
        att = Attachment(entry_id=note, filename=name, stored_name=stored,
                         mime=str(item.get("mime") or "application/octet-stream")[:100], size=len(data))
        self.session.add(att)
        self.session.flush()
        sync_state.save_arrived(self.data_dir, "file", item["sid"], att.id, sync_extras.mark(att))
        manager.log_action(self.session, "edited", "entry", note, f"a file from the other computer: {name}")
        return "applied"

    def remove_file(self, sid: str) -> None:
        local = self.names.local("file", sid)
        att = self.session.get(Attachment, local) if local is not None else None
        if att is not None:
            (self.data_dir / "uploads" / att.stored_name).unlink(missing_ok=True)
            self.session.delete(att)
            manager.log_action(self.session, "edited", "entry", att.entry_id, f"a file removed on the other computer: {att.filename}")
        if not sid.startswith(f"{self.me}:"):
            self.marks.append(("file", sid, None, ""))


def _key(kind: str, sid: str) -> str:
    return f"{kind}|{sid}"


def _wanted(session: Session, data_dir: Path, me: str, peer: str, lines: list[dict]) -> tuple[dict, set, dict]:
    """The sids to fetch by kind, those changed only there (taken whatever the times), and the
    hashes both sides now agree on.

    Three-way, against the hash both had at the last sync: a removed row (a
    drawing rubbed out) changes no time, so the times alone would let the
    other side's older copy bring it back."""
    here = {_key(x["kind"], x["sid"]): x["hash"] for x in sync_extras.manifest(session, data_dir, me)["items"]}
    base = sync_state.peer(data_dir, peer).get("synced")
    base = base if isinstance(base, dict) else {}
    out: dict[str, list[str]] = {kind: [] for kind in sync_extras.KINDS}
    force, agreed = set(), {}
    for line in lines:
        key, theirs = _key(line["kind"], line["sid"]), line["hash"]
        mine, was = here.get(key), base.get(key)
        if theirs and mine == theirs:
            agreed[key] = theirs
            continue
        if not theirs or (line["kind"] == "file" and mine is not None):
            continue
        if was == theirs or (mine is None and line["sid"].startswith(f"{me}:")):
            continue  # changed or removed only here (one of this notebook's own is never fetched back)
        out[line["kind"]].append(line["sid"])
        if mine is None or was == mine:
            force.add(line["sid"])
    return out, force, agreed


def _gone_files(data_dir: Path, me: str, peer: str, lines: list[dict]) -> list[str]:
    """Files removed on the other computer: ones that came from there, or of this notebook's it had listed."""
    listed = {x["sid"] for x in lines if x["kind"] == "file"}
    came = [s for s in sync_state.arrived(data_dir).get("file", {}) if s.startswith(f"{peer}:")]
    seen = sync_state.peer(data_dir, peer).get("seen_files") or []
    return [s for s in came + [s for s in seen if isinstance(s, str)] if s not in listed]


def _apply_kind(session: Session, link: Any, apply: Apply, kind: str, sids: list[str],  # noqa: PLR0913
                report: dict, agreed: dict, hashes: dict) -> None:
    for start in range(0, len(sids), sync_extras.MAX_ITEMS):
        for item in link.items(kind, sids[start:start + sync_extras.MAX_ITEMS], apply.me):
            if not (isinstance(item, dict) and item.get("kind") == kind and item.get("sid") in sids):
                continue
            outcome = getattr(apply, kind)(item)
            report[outcome] += 1
            session.commit()
            if outcome == "applied":
                agreed[_key(kind, item["sid"])] = hashes[_key(kind, item["sid"])]
        apply.flush()


def _apply_files(session: Session, link: Any, apply: Apply, sids: list[str], report: dict) -> None:
    for start in range(0, len(sids), sync_extras.MAX_ITEMS):
        for item in link.items("file", sids[start:start + sync_extras.MAX_ITEMS], apply.me):
            if isinstance(item, dict) and item.get("sid") in sids:
                known = apply._note_id(item.get("note")) is not None  # noqa: SLF001
                report[apply.file(item, link.file(item["sid"], apply.me) if known else None)] += 1
                session.commit()
        apply.flush()


def pull_extras(session: Session, data_dir: Path, link: Any, me: str, both: sync_keys.Keys | None) -> dict[str, int]:
    """Documents, boards and files from the paired computer; counts by outcome."""
    peer = link.name
    lines = checked(link.manifest(me), peer)
    apply = Apply(session, data_dir, me, peer, both)
    report = {"applied": 0, "same": 0, "conflicts": 0, "waiting": 0}
    wanted, apply.force, agreed = _wanted(session, data_dir, me, peer, lines)
    hashes = {_key(x["kind"], x["sid"]): x["hash"] for x in lines}
    try:
        with events.acting_as(f"sync:{peer}"), impersonate_workspace(session, ""):
            for kind in ("document", "board"):
                _apply_kind(session, link, apply, kind, wanted[kind], report, agreed, hashes)
                if kind == "document":
                    apply.link_parents()
            _apply_files(session, link, apply, wanted["file"][:MAX_FILES], report)
            for sid in _gone_files(data_dir, me, peer, lines):
                apply.remove_file(sid)
                session.commit()
    finally:
        apply.flush()
    own = sorted(x["sid"] for x in lines if x["kind"] == "file" and x["sid"].startswith(f"{me}:"))
    sync_state.save_peer(data_dir, peer, seen_files=own, synced=agreed)
    return report
