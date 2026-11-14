"""WORLD_CLASS_PLAN section 1.3's open "act on this" rows (section 8, row 15).

A reminder carried an `entry_id` only, so a document could not have one, and
a board's said "Open its note". Now a reminder points at a document too
(`document_id`), names what it points at (`target_kind`, `target_title`), and
the Library's and the boards' menus offer Remind me; a document's card offers
Show in graph; the Library's note card has its twin's Remind me and Link to.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
#: The board code and the Boards & maps gallery split out of it (INBOX 1772).
BOARDS = "".join(frontend_text(n) for n in ("whiteboard.js", "boards-gallery.js"))


def _soon() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


def test_a_reminder_can_point_at_a_document(client):
    doc = client.post("/documents", json={"title": "Grant draft", "content": "# Grant draft"}).json()
    made = client.post("/reminders", json={"text": "Send it", "due_at": _soon(), "document_id": doc["id"]})
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["document_id"] == doc["id"]
    assert body["target_kind"] == "document"
    assert body["target_title"] == "Grant draft"
    listed = client.get("/reminders", params={"document_id": doc["id"]}).json()
    assert [r["id"] for r in listed] == [body["id"]]


def test_a_reminder_on_a_missing_document_is_refused(client):
    made = client.post("/reminders", json={"text": "x", "due_at": _soon(), "document_id": 999})
    assert made.status_code == 404


def test_a_reminder_on_a_board_says_it_is_a_board(client):
    board = client.post("/whiteboard/boards", json={"name": "Kiln plan"})
    assert board.status_code in (200, 201), board.text
    board_id = board.json()["id"]
    made = client.post("/reminders", json={"text": "Look again", "due_at": _soon(), "entry_id": board_id}).json()
    assert made["target_kind"] in ("board", "map")
    assert made["target_title"] == "Kiln plan"


def test_a_note_reminder_names_its_note(client):
    note = client.post("/entries", json={"content": "# Call the plumber\n\nTuesday"}).json()
    made = client.post("/reminders", json={"text": "Call", "due_at": _soon(), "entry_id": note["id"]}).json()
    assert made["target_kind"] == "note"
    assert made["target_title"] == "Call the plumber"


def test_the_menus_offer_the_rows():
    note = LIBRARY.split('if (item.kind === "note") {', 1)[1].split("if (item.kind === \"tag\")", 1)[0]
    assert "remindAbout(" in note
    assert "linkNoteFromLibrary(" in note
    document = LIBRARY.split('if (item.kind === "document" || item.kind === "diagram") {', 1)[1].split('if (item.kind === "archived") {', 1)[0]
    assert "remindAbout(" in document
    #: The note's door takes a document too (note-cards.js, `{ document: true }`).
    assert "showNoteInGraph(item.id, { document: true })" in document
    assert "remindAbout(" in BOARDS
    assert "function remindAbout(" in LIBRARY
