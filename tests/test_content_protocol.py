"""One `Content` protocol, one bin guard (audit 1031 row 2a: BK2, DC8, AR7).

A binned note already refused a PUT (`test_bin_guard_1031.py`); the other three
content types each wrote their own bin and each answered differently: a binned
document 404 (it read as gone), a binned board 404, and a file on a binned note
200, renamed and rewritten under a note nobody could see. `repo/content.py`
owns the answer for all four, one sentence per noun, and a read keeps its 404.
"""

from __future__ import annotations

import pytest


def _note(client, text="a note about tram times") -> int:
    r = client.post("/entries", json={"content": text})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _document(client) -> int:
    r = client.post("/documents", json={"title": "Plan", "content": "first words"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _board(client) -> int:
    r = client.post("/whiteboard/boards", json={"name": "Trip plan"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _file(client) -> tuple[int, int]:
    note = _note(client, "host note")
    made = client.post(f"/entries/{note}/files", files={"file": ("handout.md", b"# Handout\n\nwords", "text/markdown")})
    assert made.status_code in (200, 201), made.text
    body = made.json()
    return note, body["id"] if "files" not in body else body["files"][0]["id"]


def test_a_binned_document_refuses_a_put_and_keeps_its_words(client):
    did = _document(client)
    binned = client.delete(f"/documents/{did}")
    assert binned.status_code == 200
    r = client.put(f"/documents/{did}", json={"content": "rewritten while binned"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "This document is in the bin. Restore it first."
    read = client.get(f"/documents/{did}")
    assert read.status_code == 404
    back = client.post(f"/documents/{did}/restore")
    assert back.status_code == 200
    kept = client.get(f"/documents/{did}").json()
    assert kept["content"] == "first words"
    again = client.put(f"/documents/{did}", json={"content": "back"})
    assert again.status_code == 200


@pytest.mark.parametrize(
    "write",
    [
        lambda client, bid: client.put(f"/whiteboard/boards/{bid}", json={"name": "Renamed"}),
        lambda client, bid: client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "hi"}, "board_id": bid}),
    ],
    ids=["rename", "add-object"],
)
def test_a_binned_board_refuses_a_write(client, write):
    bid = _board(client)
    binned = client.delete(f"/entries/{bid}")
    assert binned.status_code == 200
    r = write(client, bid)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "This board is in the bin. Restore it first."
    back = client.post(f"/entries/{bid}/restore")
    assert back.status_code == 200
    again = write(client, bid)
    assert again.status_code in (200, 201)


@pytest.mark.parametrize(
    "write",
    [
        lambda client, fid: client.put(f"/files/{fid}", json={"filename": "renamed.md"}),
        lambda client, fid: client.put(f"/files/{fid}/text", json={"text": "# Rewritten"}),
    ],
    ids=["rename", "save-text"],
)
def test_a_file_on_a_binned_note_refuses_a_write(client, write):
    note, fid = _file(client)
    binned = client.delete(f"/entries/{note}")
    assert binned.status_code == 200
    r = write(client, fid)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "This file is in the bin. Restore it first."
    back = client.post(f"/entries/{note}/restore")
    assert back.status_code == 200
    again = write(client, fid)
    assert again.status_code == 200


def test_an_unknown_id_is_still_404_for_every_kind(client):
    answers = [
        client.put("/documents/987654", json={"content": "x"}),
        client.put("/whiteboard/boards/987654", json={"name": "x"}),
        client.put("/files/987654", json={"filename": "x.md"}),
        client.put("/entries/987654", json={"content": "x"}),
    ]
    assert [r.status_code for r in answers] == [404, 404, 404, 404]


def test_every_kind_is_one_adapter_behind_one_guard():
    from tessellate.repo import content

    assert set(content.KINDS) == {"note", "board", "document", "file", "reminder", "recording"}
    for adapter in content.KINDS.values():
        assert isinstance(adapter, content.Content)


# --- step (2): one undo table ------------------------------------------------


def _reminder(client) -> int:
    r = client.post("/reminders", json={"text": "water the plants", "due_at": "2099-01-01T09:00:00"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _recording(client) -> int:
    r = client.post("/recordings", json={"title": "Standup", "mime": "audio/webm;codecs=opus"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


#: kind: (make, the route that bins it).
BINNABLE = {
    "note": (_note, "/entries/{}"),
    "board": (_board, "/entries/{}"),
    "document": (_document, "/documents/{}"),
    "reminder": (_reminder, "/reminders/{}"),
    "recording": (_recording, "/recordings/{}"),
}


@pytest.mark.parametrize("kind", sorted(BINNABLE))
def test_the_bin_restores_every_kind_through_one_route(client, kind):
    make, bin_route = BINNABLE[kind]
    row = make(client)
    binned = client.delete(bin_route.format(row))
    assert binned.status_code == 200
    back = client.post(f"/bin/{kind}/{row}/restore")
    assert back.status_code == 200, back.text
    assert back.json() == {"kind": kind, "id": row, "restored": True}
    again = client.post(f"/bin/{kind}/{row}/restore")
    assert again.json()["restored"] is False, "a live row is left as it is"
    rebinned = client.delete(bin_route.format(row))
    assert rebinned.status_code == 200, "it was live again"


def test_the_one_route_answers_404_for_no_row_and_no_kind(client):
    missing = client.post("/bin/document/987654/restore")
    assert missing.status_code == 404
    unknown = client.post("/bin/spaceship/1/restore")
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Nothing of that kind goes in the bin."


@pytest.mark.parametrize("kind", ["note", "board", "document", "reminder", "recording"])
def test_restore_flushes_and_never_commits(session, kind):
    """The undo table is a repository verb: the caller's commit decides."""
    from tessellate.core.database import Document, Entry, Recording, Reminder, utcnow
    from tessellate.repo import content

    if kind in ("note", "board"):
        row = Entry(content="binned", is_deleted=True, deleted_at=utcnow(), is_board=kind == "board")
    elif kind == "document":
        row = Document(title="binned", content="", deleted_at=utcnow())
    elif kind == "reminder":
        row = Reminder(text="binned", due_at=utcnow(), deleted_at=utcnow())
    else:
        row = Recording(title="binned", deleted_at=utcnow())
    session.add(row)
    session.commit()
    restored, was_binned = content.restore(session, kind, row.id)
    assert restored is row and was_binned
    assert not content.KINDS[kind].is_binned(session, row)
    session.rollback()
    session.expire_all()
    assert content.KINDS[kind].is_binned(session, content.KINDS[kind].find_any(session, row.id))


def test_manager_restore_entry_flushes_and_never_commits(session):
    from tessellate.core.database import Entry, utcnow
    from tessellate.entry import manager

    entry = Entry(content="binned", is_deleted=True, deleted_at=utcnow())
    session.add(entry)
    session.commit()
    manager.restore_entry(session, entry)
    session.rollback()
    session.expire_all()
    assert session.get(Entry, entry.id).is_deleted


def test_the_library_bin_restores_through_the_one_route():
    """`binRoutes` named five restore routes; it names one (and readings keep
    theirs: a binned reading is a former value of a file's text, not a row)."""
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend/js/library.js").read_text(encoding="utf-8")
    body = js.split("function binRoutes(item) {")[1].split("\n}\n")[0]
    assert "restore: `/bin/${item.subtype}/${item.id}/restore`" in body
    for old in ("/documents/${item.id}/restore", "/reminders/${item.id}/restore", "/recordings/${item.id}/restore", "/entries/${item.id}/restore"):
        assert old not in body, old


def test_a_binned_board_refuses_a_thumbnail_and_its_reads_stay_404(client):
    """A thumbnail PUT is a write, so it answers the bin guard's 409; it used to
    share the reads' lookup and say 404, as if the board were gone."""
    bid = _board(client)
    binned = client.delete(f"/entries/{bid}")
    assert binned.status_code == 200
    webp = b"RIFF" + (100).to_bytes(4, "little") + b"WEBP" + b"VP8 " + b"\x00" * 90
    put = client.put(f"/whiteboard/boards/{bid}/thumbnail?fp={'a' * 16}", content=webp)
    assert put.status_code == 409, put.text
    assert put.json()["detail"] == "This board is in the bin. Restore it first."
    state = client.get(f"/whiteboard/boards/{bid}/thumbnail/state")
    assert state.status_code == 404
    back = client.post(f"/bin/board/{bid}/restore")
    assert back.status_code == 200
    again = client.put(f"/whiteboard/boards/{bid}/thumbnail?fp={'a' * 16}", content=webp)
    assert again.status_code == 200


@pytest.mark.parametrize("kind", sorted(BINNABLE))
def test_every_kind_purges_by_the_method_the_library_sends(client, kind):
    """The Library's "Delete for good" sends DELETE to each kind's purge; a
    recording's answered only POST, so it said 405 (driven on :8855)."""
    make, bin_route = BINNABLE[kind]
    row = make(client)
    binned = client.delete(bin_route.format(row))
    assert binned.status_code == 200
    purged = client.delete(bin_route.format(row) + "/purge")
    assert purged.status_code == 200, purged.text


# --- step (3): one export walker ---------------------------------------------


def test_walk_yields_every_kind_in_one_order(session):
    """Notes and boards in id order (one pass, as the folder export writes
    them), then documents, then files: every row the session reads, a binned
    note included, each with its adapter."""
    from tessellate.core.database import Attachment, Document, Entry, utcnow
    from tessellate.repo import content

    note = Entry(content="a note")
    board = Entry(content="a board", is_board=True)
    binned = Entry(content="binned", is_deleted=True, deleted_at=utcnow())
    session.add_all([note, board, binned])
    session.flush()
    doc = Document(title="Plan", content="words")
    session.add(doc)
    session.flush()
    session.add(Attachment(entry_id=note.id, filename="a.md", stored_name="walk-a.md"))
    session.commit()
    walked = [(adapter.kind, row.id) for adapter, row in content.walk(session)]
    files = [(k, i) for k, i in walked if k == "file"]
    assert walked[:3] == [("note", note.id), ("board", board.id), ("note", binned.id)]
    assert walked.index(("document", doc.id)) < walked.index(files[0])
    some = [(adapter.kind, row.id) for adapter, row in content.walk(session, ("document",))]
    assert some == [("document", doc.id)]


def test_the_exports_read_the_walker():
    """The folder export, its snapshot and the JSON, CSV and Markdown exports
    walk `repo/content.walk` rather than each selecting its own rows."""
    import inspect

    from tessellate.api import routes_settings_transfer
    from tessellate.entry import export_folder

    for fn in (export_folder.snapshot, export_folder.export, export_folder._write_documents, routes_settings_transfer._export_rows):
        source = inspect.getsource(fn)
        assert "walk(session" in source, fn.__name__
        assert "select(Entry)" not in source and "select(Document)" not in source, fn.__name__


# --- content3: a binned document is exported like a binned note ----------------


def _folder_export(session):
    import io
    import json
    import zipfile

    from tessellate.core import deps
    from tessellate.entry import export_folder

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        export_folder.export(session, deps.get_config().uploads_dir, archive)
    folder = zipfile.ZipFile(io.BytesIO(buffer.getvalue()))
    return folder, json.loads(folder.read("index.json"))


def test_the_folder_export_carries_a_binned_note_and_a_binned_document(client):
    """The decision (row 2a): a binned document is walked like a binned note,
    so the folder export never silently drops what the bin still holds."""
    from tessellate.core import deps

    kept_note, gone_note = _note(client, "a kept note"), _note(client, "a binned note")
    kept_doc, gone_doc = _document(client), _document(client)
    reply = client.delete(f"/entries/{gone_note}")
    assert reply.status_code == 200
    reply = client.delete(f"/documents/{gone_doc}")
    assert reply.status_code == 200
    session = deps.get_db().session()
    try:
        folder, index = _folder_export(session)
    finally:
        session.close()
    names = folder.namelist()
    assert any(n.startswith(f"notes/_recycle-bin/{gone_note}-") for n in names)
    assert index["counts"]["documents"] == 2
    ids = {d["id"] for d in index["documents"]}
    assert ids == {kept_doc, gone_doc}
    binned = [d for d in index["documents"] if d["id"] == gone_doc][0]
    assert binned["md"].startswith("documents/_recycle-bin/")
    assert kept_note and folder.read(binned["md"]).decode() == "first words"


def test_a_reimport_does_not_duplicate_a_binned_document(client):
    """`_existing_documents` reads the bin, so the same folder read in again
    merges its binned document rather than making a second copy."""
    from sqlalchemy import select

    from tessellate.core import deps
    from tessellate.core.database import Document
    from tessellate.entry import export_folder
    from tessellate.entry.bin import including_binned

    gone = _document(client)
    reply = client.delete(f"/documents/{gone}")
    assert reply.status_code == 200
    session = deps.get_db().session()
    try:
        folder, _ = _folder_export(session)
        files = [(n, folder.read(n)) for n in folder.namelist()]
        notes, _skipped, extra = export_folder.read(files)
        result = type("R", (), {"notes": notes, "extra": extra})()
        export_folder.write(session, result, deps.get_config().uploads_dir)
        session.commit()
        with including_binned(session):
            assert len(list(session.scalars(select(Document)))) == 1
    finally:
        session.close()


# --- content3: the reminder and recording write routes ask the same guard ------


def _notification_act(client, rid):
    from tessellate.core import deps, reminder_token

    token = reminder_token.mint(rid, data_dir=deps.get_config().data_dir)["token"]
    return client.post(f"/reminders/{rid}/notification-act", json={"token": token, "action": "done"})


REMINDER_WRITES = {
    "put": lambda client, rid: client.put(f"/reminders/{rid}", json={"text": "rewritten"}),
    "complete": lambda client, rid: client.post(f"/reminders/{rid}/complete"),
    "notification-act": _notification_act,
    "delete": lambda client, rid: client.delete(f"/reminders/{rid}"),
}

RECORDING_WRITES = {
    "patch": lambda client, rid: client.patch(f"/recordings/{rid}", json={"title": "rewritten"}),
    "finish": lambda client, rid: client.post(f"/recordings/{rid}/finish", json={}),
    "transcribe": lambda client, rid: client.post(f"/recordings/{rid}/transcribe"),
    "transcribe-start": lambda client, rid: client.post(f"/recordings/{rid}/transcribe/start"),
    "transcribe-stop": lambda client, rid: client.post(f"/recordings/{rid}/transcribe/stop"),
    "speakers-name": lambda client, rid: client.post(f"/recordings/{rid}/speakers"),
    "speakers-rename": lambda client, rid: client.put(
        f"/recordings/{rid}/speakers", json={"from_name": "A", "to_name": "B"}),
    "delete": lambda client, rid: client.delete(f"/recordings/{rid}"),
}


@pytest.mark.parametrize("write", sorted(REMINDER_WRITES))
def test_a_binned_reminder_refuses_every_write_with_the_guards_409(client, write):
    rid = _reminder(client)
    reply = client.delete(f"/reminders/{rid}")
    assert reply.status_code == 200
    r = REMINDER_WRITES[write](client, rid)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "This reminder is in the bin. Restore it first."
    reply = client.get(f"/reminders/{rid}/export.ics")
    assert reply.status_code == 404, "a read keeps its 404"


@pytest.mark.parametrize("write", sorted(RECORDING_WRITES))
def test_a_binned_recording_refuses_every_write_with_the_guards_409(client, write):
    rid = _recording(client)
    reply = client.delete(f"/recordings/{rid}")
    assert reply.status_code == 200
    r = RECORDING_WRITES[write](client, rid)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "This recording is in the bin. Restore it first."
    reply = client.get(f"/recordings/{rid}")
    assert reply.status_code == 404, "a read keeps its 404"


@pytest.mark.parametrize("kind", ["reminder", "recording"])
def test_an_unknown_reminder_or_recording_write_is_404_in_the_guards_words(client, kind):
    writes = REMINDER_WRITES if kind == "reminder" else RECORDING_WRITES
    for name, write in writes.items():
        r = write(client, 987654)
        assert r.status_code == 404, (name, r.text)
        assert r.json()["detail"] == f"That {kind} could not be found.", name
