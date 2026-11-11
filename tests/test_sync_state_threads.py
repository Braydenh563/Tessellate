"""sync-state.json under threads, and the manifest's per-file cost (PR 216 review)."""

from __future__ import annotations

import os
import threading

from sqlalchemy import event

from tessellate.core import sync_state
from tessellate.core.database import Attachment
from tessellate.core.database_manager import DatabaseManager
from tessellate.entry import manager, sync_extras


def test_concurrent_writers_lose_no_update_and_raise_nothing(tmp_path):
    errors: list[BaseException] = []

    def work(n: int) -> None:
        try:
            for i in range(10):
                sync_state.save_peer(tmp_path, f"peer{n}-{i}", cursor=n * 100 + i + 1)
                sync_state.issue_pass(tmp_path, f"dev{n}-{i}")
                sync_state.save_link(tmp_path, **{f"k{n}_{i}": i})
                sync_state.device_id(tmp_path)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    state = sync_state._read(tmp_path)  # noqa: SLF001
    assert len(state["peers"]) == 80 and len(state["passes"]) == 80 and len(state["link"]) == 80
    assert (os.stat(tmp_path / sync_state.FILE_NAME).st_mode & 0o777) == 0o600
    assert [p.name for p in tmp_path.iterdir()] == [sync_state.FILE_NAME]


def test_save_arrived_many_is_one_write(tmp_path, monkeypatch):
    writes = []
    real = sync_state._write  # noqa: SLF001
    monkeypatch.setattr(sync_state, "_write", lambda d, s: (writes.append(1), real(d, s)))
    sync_state.save_arrived_many(tmp_path, [("file", f"x:{i}", i + 1, "m") for i in range(20)] + [("file", "x:3", None, "")])
    assert len(writes) == 1
    assert len(sync_state.arrived(tmp_path)["file"]) == 19


def _attach(session, uploads, note, name, data):
    (uploads / name).write_bytes(data)
    att = Attachment(entry_id=note.id, filename=name, stored_name=name, mime="x/y", size=len(data))
    session.add(att)
    session.commit()
    return att


def test_an_unchanged_file_is_hashed_once_and_a_changed_one_again(tmp_path, monkeypatch):
    sync_extras._SHA1_CACHE.clear()  # noqa: SLF001
    path = tmp_path / "f.bin"
    path.write_bytes(b"one")
    reads = []
    real = type(path).read_bytes
    monkeypatch.setattr(type(path), "read_bytes", lambda self: (reads.append(self), real(self))[1])
    first = sync_extras._file_sha1(path, "f.bin")  # noqa: SLF001
    assert sync_extras._file_sha1(path, "f.bin") == first and len(reads) == 1  # noqa: SLF001
    path.write_bytes(b"three")
    assert sync_extras._file_sha1(path, "f.bin") != first and len(reads) == 2  # noqa: SLF001


def test_rows_load_the_notes_in_one_query(app_state, tmp_path):
    session = DatabaseManager(tmp_path / "memorymap.db").session()
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    note = manager.create_entry(session, "a note")
    for i in range(6):
        _attach(session, uploads, note, f"f{i}.bin", bytes([i]))
    session.expire_all()
    seen: list[str] = []
    event.listen(session.get_bind(), "before_cursor_execute", lambda c, cur, st, p, ctx, many: seen.append(st))
    names = sync_extras.Names(session, "abcdefabcdef", {})
    rows = list(sync_extras._rows(session, names, uploads))  # noqa: SLF001
    assert len([r for r in rows if r[1] == "file"]) == 6
    assert len([s for s in seen if "FROM entries" in s]) <= 1, seen
