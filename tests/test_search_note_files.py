"""A note's pictures' captions, OCR and vision text are part of the note's own search row (L564)."""

from __future__ import annotations

from sqlalchemy import text

from tessellate.core.database import Attachment
from tessellate.entry import manager
from tessellate.search import index


def _body(session, entry_id: int) -> str:
    source = index.source_for("notes")
    row = session.connection().exec_driver_sql("SELECT body FROM search_index WHERE rowid = ?", (index._rowid(source, entry_id),)).first()  # noqa: SLF001
    return row[0] if row else ""


def _note(session) -> int:
    entry = manager.create_entry(session, "Holiday photos", category_name=manager.UNCATEGORISED)
    session.commit()
    return entry.id


def test_a_files_readings_join_its_notes_row_when_it_is_added_and_when_it_is_read_again(session):
    note = _note(session)
    att = Attachment(entry_id=note, filename="a.png", stored_name="n1", size=1, caption="A heron on the estuary")
    session.add(att)
    session.commit()
    assert "heron on the estuary" in _body(session, note) and _body(session, note).startswith("Holiday photos")
    att.ocr_text = "Quayside cafe menu"
    session.commit()
    assert "Quayside cafe menu" in _body(session, note)
    session.delete(att)
    session.commit()
    assert _body(session, note) == "Holiday photos"


def test_a_page_read_by_a_job_reaches_the_note_through_touch(session):
    note = _note(session)
    att = Attachment(entry_id=note, filename="scan.pdf", stored_name="n2", size=1)
    session.add(att)
    session.commit()
    session.execute(text("INSERT INTO page_reads (kind, source_id, page, text, caption, reader, model, caption_model, regions, created_at) VALUES ('attachment', :id, 1, 'Boiler warranty ends in May', '', 'test', 'test', '', '[]', '2026-11-12')"), {"id": att.id})
    index.touch(session, "attachments", att.id)
    assert "Boiler warranty ends in May" in _body(session, note)


def test_a_private_notes_files_are_not_folded_in_and_the_startup_diff_fills_an_old_row(session):
    note = _note(session)
    att = Attachment(entry_id=note, filename="a.png", stored_name="n3", size=1, caption="Lighthouse at dusk")
    session.add(att)
    session.commit()
    source = index.source_for("notes")
    index._write(session.connection(), source, note, index.Row(title="Holiday photos", body="Holiday photos"))  # noqa: SLF001
    assert "Lighthouse" not in _body(session, note)
    assert index.reconcile_note_files(session) is True
    assert "Lighthouse at dusk" in _body(session, note)
    assert index.reconcile_note_files(session) is False
