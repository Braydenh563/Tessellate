"""Where a note came from (L-general-13): `source_kind` and `source_label` on
every entry, derived from `source_url`, `source_path` and a recording's
transcript. A note typed by hand has neither."""

from __future__ import annotations

import json

import pytest

from tessellate.core.database import Entry, Recording
from tessellate.entry import provenance


@pytest.mark.parametrize(
    ("url", "path", "heard", "kind", "label"),
    [
        (None, "", False, "", ""),
        ("https://www.example.org/a/b", "", False, "url", "Clipped from example.org"),
        (None, "Reports/q3.pdf", False, "document", "Extracted from q3.pdf"),
        (None, "document", False, "document", "Extracted from a document"),
        (None, "Projects/Roadmap.md", False, "file", "Imported from Roadmap.md"),
        (None, "notion:abc123", False, "file", "Imported from Notion"),
        (None, "", True, "audio", "Transcribed from audio"),
        ("https://a.test/", "x.md", True, "url", "Clipped from a.test"),
    ],
)
def test_kind_is_derived_from_what_the_note_already_has(url, path, heard, kind, label) -> None:
    assert provenance.source_kind(url, path, heard) == (kind, label)


def _make(session, text: str, **columns) -> int:
    entry = Entry(content=text, **columns)
    session.add(entry)
    session.commit()
    return entry.id


def test_entries_carry_their_kind_in_a_list_and_alone(client, session) -> None:
    typed = _make(session, "Typed by hand")
    clipped = _make(session, "A page", source_url="https://news.test/story")
    doc = _make(session, "A section", source_path="Handbook.docx")
    vault = _make(session, "A file", source_path="Notes/Idea.md")
    spoken = _make(session, "Said aloud")
    silent = _make(session, "Recorded, not transcribed")
    session.add_all(
        [
            Recording(entry_id=spoken, segments=json.dumps([{"start": 0, "end": 900, "text": "hello", "speaker": ""}]), state="done"),
            Recording(entry_id=silent, segments="[]", state="done"),
        ]
    )
    session.commit()

    rows = {row["id"]: row for row in client.get("/entries?limit=50").json()}
    kinds = {name: rows[i]["source_kind"] for name, i in
             [("typed", typed), ("clipped", clipped), ("doc", doc), ("vault", vault), ("spoken", spoken), ("silent", silent)]}
    assert kinds == {"typed": "", "clipped": "url", "doc": "document", "vault": "file", "spoken": "audio", "silent": ""}
    assert rows[clipped]["source_label"] == "Clipped from news.test"
    alone = client.get(f"/entries/{spoken}").json()
    assert alone["source_label"] == "Transcribed from audio"
    by_hand = client.get(f"/entries/{typed}").json()
    assert by_hand["source_kind"] == ""


def test_extracted_note_says_which_document_and_survives_its_deletion(client, session) -> None:
    from tessellate.core.database import Document

    doc = Document(title="Q3 plan", content="Body")
    session.add(doc)
    session.commit()
    body = {"notes": [{"ref": "a", "content": "One idea from the plan"}], "source_document_id": doc.id}
    made = client.post("/entries/extract/commit", json=body)
    assert made.status_code == 201, made.text
    note = made.json()["notes"][0]
    assert (note["source_kind"], note["source_label"]) == ("document", "Extracted from Q3 plan")
    stored = session.get(Entry, note["id"])
    assert stored.origin_document_id == doc.id
    assert not stored.source_path  # never the injection guard's marker

    binned = client.delete(f"/documents/{doc.id}")
    assert binned.status_code == 200
    purged = client.delete(f"/documents/{doc.id}/purge")
    assert purged.status_code == 200
    session.expire_all()
    again = client.get(f"/entries/{note['id']}").json()
    assert (again["source_kind"], again["source_label"]) == ("document", "Extracted from a document")


def test_meeting_notes_are_audio_only_when_a_recording_was_transcribed(client, session) -> None:
    typed = client.post("/meetings", json={"title": "Weekly sync", "notes": "Talked"}).json()
    assert typed["source_kind"] == ""
    segments = json.dumps([{"start": 0, "end": 900, "text": "hi", "speaker": ""}])
    session.add(Recording(entry_id=typed["id"], segments=segments, state="done"))
    session.commit()
    heard = client.get(f"/entries/{typed['id']}").json()
    assert heard["source_kind"] == "audio"
