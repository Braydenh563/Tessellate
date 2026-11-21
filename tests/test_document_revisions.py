"""A document's edit history: asked for by name: "can the document have edit
history like git logs??"

Notes have had `EntryRevision` for a long time; documents had nothing. Rewriting
one destroyed what it used to say, with nothing but the session's own undo
stack, which forgets on reload. `DocumentAiEdit` covered the *AI's* edits only: 
a person's own rewrite left no trace at all.

The interesting behaviour, and what these tests pin down, is the coalescing.
Autosave fires while you type, so a naive "one row per save" history is two
hundred entries five seconds apart: a keylogger, not a log.
"""

from __future__ import annotations

from datetime import timedelta

from tessellate.api import routes_documents
from tessellate.core.database import DocumentRevision, utcnow
import pytest
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)


def _make(client, content="First version."):
    return client.post("/documents", json={"title": "Doc", "content": content}).json()


def test_a_new_document_has_no_history(client):
    doc = _make(client)
    assert client.get(f"/documents/{doc['id']}/revisions").json() == []


def test_an_edit_keeps_what_it_replaced(client):
    doc = _make(client, "The first version.")
    client.put(f"/documents/{doc['id']}", json={"content": "The second version."})
    rows = client.get(f"/documents/{doc['id']}/revisions").json()
    assert len(rows) == 1
    kept = client.get(f"/documents/{doc['id']}/revisions/{rows[0]['id']}").json()
    assert kept["content"] == "The first version.", "the revision is the version replaced"


def test_a_title_only_change_is_not_history(client):
    """Nothing happened to the text, so the history must not claim it did."""
    doc = _make(client)
    client.put(f"/documents/{doc['id']}", json={"title": "Renamed"})
    assert client.get(f"/documents/{doc['id']}/revisions").json() == []


def test_an_identical_autosave_is_not_history(client):
    doc = _make(client, "Unchanged.")
    client.put(f"/documents/{doc['id']}", json={"content": "Unchanged."})
    assert client.get(f"/documents/{doc['id']}/revisions").json() == []


def test_a_burst_of_editing_is_one_entry(client):
    """Autosave while typing must not become a hundred rows."""
    doc = _make(client, "v0")
    for n in range(1, 6):
        client.put(f"/documents/{doc['id']}", json={"content": f"v{n}"})
    rows = client.get(f"/documents/{doc['id']}/revisions").json()
    assert len(rows) == 1, "one sitting is one entry"


def test_editing_again_later_is_a_second_entry(client, db_session_factory=None):
    """Coming back after a gap starts a new entry."""
    doc = _make(client, "v0")
    client.put(f"/documents/{doc['id']}", json={"content": "v1"})
    # Age the existing revision past the quiet window, as time would.
    with routes_documents.deps.get_db().session() as session:
        row = session.query(DocumentRevision).one()
        row.created_at = utcnow() - timedelta(
            seconds=routes_documents.REVISION_QUIET_SECONDS + 60
        )
        session.commit()
    client.put(f"/documents/{doc['id']}", json={"content": "v2"})
    rows = client.get(f"/documents/{doc['id']}/revisions").json()
    assert len(rows) == 2


def test_the_list_says_how_big_each_change_was(client):
    """A history where every row looks the same has to be read linearly."""
    doc = _make(client, "one two three")
    client.put(f"/documents/{doc['id']}", json={"content": "one two three four five"})
    row = client.get(f"/documents/{doc['id']}/revisions").json()[0]
    assert row["words"] == 3
    assert row["word_delta"] == 2, "against the version that replaced it"


def test_restoring_puts_the_text_back_and_keeps_the_one_it_replaced(client):
    doc = _make(client, "The original.")
    client.put(f"/documents/{doc['id']}", json={"content": "A rewrite nobody wanted."})
    rows = client.get(f"/documents/{doc['id']}/revisions").json()
    restored = client.post(f"/documents/{doc['id']}/revisions/{rows[0]['id']}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["content"] == "The original."
    # Restoring the wrong entry must itself be undoable.
    after = client.get(f"/documents/{doc['id']}/revisions").json()
    assert any(entry["source"] == "restore" for entry in after)


def test_a_revision_from_another_document_is_a_404(client):
    a = _make(client, "A")
    b = _make(client, "B")
    client.put(f"/documents/{a['id']}", json={"content": "A2"})
    revision = client.get(f"/documents/{a['id']}/revisions").json()[0]["id"]
    assert client.get(f"/documents/{b['id']}/revisions/{revision}").status_code == 404
    assert (
        client.post(f"/documents/{b['id']}/revisions/{revision}/restore").status_code == 404
    )


def test_the_history_is_bounded(client):
    """A table that grows without bound is a table that eventually is the app."""
    doc = _make(client, "v0")
    for n in range(1, routes_documents.MAX_DOCUMENT_REVISIONS + 12):
        client.put(f"/documents/{doc['id']}", json={"content": f"v{n}"})
        with routes_documents.deps.get_db().session() as session:
            row = (
                session.query(DocumentRevision)
                .order_by(DocumentRevision.id.desc())
                .first()
            )
            if row is not None:
                row.created_at = utcnow() - timedelta(
                    seconds=routes_documents.REVISION_QUIET_SECONDS + 60
                )
                session.commit()
    rows = client.get(f"/documents/{doc['id']}/revisions").json()
    assert len(rows) <= routes_documents.MAX_DOCUMENT_REVISIONS


def test_deleting_a_document_takes_its_history_with_it(client):
    """A real foreign key with no ORM cascade: the delete failed outright.

    Caught by the whole suite rather than by the tests for the thing I touched
    - `test_documents_api.py::test_create_read_update_delete` started raising
    `FOREIGN KEY constraint failed` the moment revisions began being written.
    Kept here as well, close to the cause.
    """
    doc = _make(client, "before")
    client.put(f"/documents/{doc['id']}", json={"content": "after"})
    assert client.get(f"/documents/{doc['id']}/revisions").json(), "a revision exists"
    deleted = client.delete(f"/documents/{doc['id']}")
    assert deleted.status_code == 200
    #: The bin keeps the history until the document is purged (5 item 10).
    response = client.delete(f"/documents/{doc['id']}/purge")
    assert response.status_code == 200
    with routes_documents.deps.get_db().session() as session:
        left = (
            session.query(DocumentRevision)
            .filter(DocumentRevision.document_id == doc["id"])
            .count()
        )
    assert left == 0, "a deleted document must not leave its text behind"


# --- named versions (DOCUMENTS_PLAN 24 row 4, Brief 76) ----------------------


def test_naming_the_current_version_keeps_its_text_through_later_edits(client):
    """Google Docs's "Name current version": the named row holds the text as it
    stood, and the edits after it never coalesce into it."""
    doc = _make(client, "Draft one.")
    named = client.post(f"/documents/{doc['id']}/revisions", json={"name": "Sent to Sam"})
    assert named.status_code == 201 and named.json()["name"] == "Sent to Sam"
    for n in range(3):
        client.put(f"/documents/{doc['id']}", json={"content": f"Draft one, edit {n}."})
    rows = client.get(f"/documents/{doc['id']}/revisions").json()
    kept = [row for row in rows if row["name"] == "Sent to Sam"]
    assert len(kept) == 1
    body = client.get(f"/documents/{doc['id']}/revisions/{kept[0]['id']}").json()
    assert body["content"] == "Draft one." and body["name"] == "Sent to Sam"
    assert len(rows) == 2, "the edits after it are one sitting of their own"


def test_a_version_is_renamed_and_unnamed_without_touching_its_text(client):
    doc = _make(client, "Alpha.")
    client.put(f"/documents/{doc['id']}", json={"content": "Beta."})
    row = client.get(f"/documents/{doc['id']}/revisions").json()[0]
    assert row["name"] is None
    did, rid = doc["id"], row["id"]
    url = f"/documents/{did}/revisions/{rid}"
    named = client.put(url, json={"name": " First cut "}).json()
    assert named["name"] == "First cut"
    kept = client.get(url).json()
    assert kept["content"] == "Alpha."
    unnamed = client.put(url, json={"name": "  "}).json()
    assert unnamed["name"] is None


def test_a_version_needs_a_name_and_belongs_to_its_document(client):
    doc = _make(client)
    other = _make(client, "Other.")
    blank = client.post(f"/documents/{doc['id']}/revisions", json={"name": " "})
    assert blank.status_code == 422
    client.put(f"/documents/{other['id']}", json={"content": "Other, edited."})
    rid = client.get(f"/documents/{other['id']}/revisions").json()[0]["id"]
    foreign = client.put(f"/documents/{doc['id']}/revisions/{rid}", json={"name": "x"})
    assert foreign.status_code == 404
