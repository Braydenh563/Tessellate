"""WORLD_CLASS_PLAN section 5 item 10 (section 8, row 30): the bin for
documents and reminders.

Notes, boards and maps went to the recycle bin and came back with
`POST /entries/{id}/restore`; a document and a reminder were deleted outright,
and their Undo made a new copy (a new id, the document's history gone). Now
both are binned: hidden everywhere, listed in the Library's bin, restored with
their id, purged by hand, by Empty the bin, or after the bin's days.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _soon() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


def _bin(client):
    items = client.get("/library").json()["items"]
    return [i for i in items if i["kind"] == "archived"]


def test_a_deleted_document_goes_to_the_bin_and_comes_back_whole(client):
    doc = client.post("/documents", json={"title": "Thesis", "content": "# Thesis\n\nChapter one."}).json()
    client.put(f"/documents/{doc['id']}", json={"content": "# Thesis\n\nChapter one, revised."})
    response = client.delete(f"/documents/{doc['id']}")
    assert response.status_code == 200

    assert client.get(f"/documents/{doc['id']}").status_code == 404
    assert doc["id"] not in [d["id"] for d in client.get("/documents").json()]
    binned = [i for i in _bin(client) if i.get("subtype") == "document"]
    assert [i["id"] for i in binned] == [doc["id"]]
    assert binned[0]["title"] == "Thesis"

    response = client.post(f"/documents/{doc['id']}/restore")
    assert response.status_code == 200
    back = client.get(f"/documents/{doc['id']}").json()
    assert back["content"] == "# Thesis\n\nChapter one, revised."
    assert not [i for i in _bin(client) if i.get("subtype") == "document"]


def test_a_binned_document_can_be_purged_and_only_a_binned_one(client):
    doc = client.post("/documents", json={"title": "Scrap", "content": "x"}).json()
    response = client.delete(f"/documents/{doc['id']}/purge")
    assert response.status_code == 409
    client.delete(f"/documents/{doc['id']}")
    response = client.delete(f"/documents/{doc['id']}/purge")
    assert response.status_code == 200
    response = client.post(f"/documents/{doc['id']}/restore")
    assert response.status_code == 404


def test_a_deleted_reminder_goes_to_the_bin_and_comes_back(client):
    made = client.post("/reminders", json={"text": "Water the plants", "due_at": _soon()}).json()
    response = client.delete(f"/reminders/{made['id']}")
    assert response.status_code == 200
    assert made["id"] not in [r["id"] for r in client.get("/reminders").json()]
    binned = [i for i in _bin(client) if i.get("subtype") == "reminder"]
    assert [i["id"] for i in binned] == [made["id"]]
    response = client.post(f"/reminders/{made['id']}/restore")
    assert response.status_code == 200
    assert made["id"] in [r["id"] for r in client.get("/reminders").json()]
    client.delete(f"/reminders/{made['id']}")
    response = client.delete(f"/reminders/{made['id']}/purge")
    assert response.status_code == 200
    response = client.post(f"/reminders/{made['id']}/restore")
    assert response.status_code == 404


def test_empty_the_bin_takes_documents_and_reminders_too(client):
    doc = client.post("/documents", json={"title": "Old", "content": "x"}).json()
    rem = client.post("/reminders", json={"text": "Old", "due_at": _soon()}).json()
    client.delete(f"/documents/{doc['id']}")
    client.delete(f"/reminders/{rem['id']}")
    response = client.post("/recycle-bin/empty")
    assert response.status_code == 200
    assert _bin(client) == []
    response = client.post(f"/documents/{doc['id']}/restore")
    assert response.status_code == 404


def test_the_bin_clears_old_documents_and_reminders_on_its_own(session):
    from tessellate.core.database import Document, Reminder, utcnow
    from tessellate.entry import bin as other_bin

    long_ago = utcnow() - timedelta(days=40)
    session.add(Document(title="Gone", content="", deleted_at=long_ago))
    session.add(Reminder(text="Gone", due_at=utcnow(), deleted_at=long_ago))
    session.add(Document(title="Kept", content="", deleted_at=utcnow()))
    session.commit()
    assert other_bin.purge_expired(session, 30) == 2
    with other_bin.including_binned(session):
        titles = [d.title for d in session.query(Document).all()]
    assert titles == ["Kept"]


def test_the_frontend_restores_rather_than_recreating():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    documents = (root / "documents.js").read_text(encoding="utf-8")
    undo = documents.split("async function deleteDocumentWithUndo(", 1)[1].split("\n}\n", 1)[0]
    assert "/restore" in undo and 'method: "POST",\n      body' not in undo
    # The row's Delete loads its handler on the press (reminder-edit.js, boot scripts' cap).
    reminders = (root / "reminder-edit.js").read_text(encoding="utf-8")
    row = reminders.split("loadReminders.binOne = async function (reminder) {", 1)[1].split("\n  };\n", 1)[0]
    assert "/restore" in row
    library = (root / "library.js").read_text(encoding="utf-8")
    assert "function binRoutes(" in library
