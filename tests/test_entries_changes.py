"""`GET /entries/changes?since=`: what another device changed (INBOX 881,
the owner 2026-10-11: "what if I make a change on my phone?? does it live
update??").

A save on the phone did not reach the computer's open list until a reload.
The client now asks, every few seconds while visible and whenever the tab
comes back, which notes changed since its last answer, and hands those ids to
`refreshEntries` (notes-list.js `followNoteChanges`). These hold the server
half: the ids moved since the stamp, a stamp to ask from next, boards left
out (the notes list does not hold them), and a cap with `more` so a bulk
change tells the client to re-read the list rather than a long id list.
"""

from __future__ import annotations

import time
from pathlib import Path


def _note(client, text, **extra):
    response = client.post("/entries", json={"content": text, "category": "Ideas", **extra})
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_first_call_is_a_stamp_with_no_ids(client):
    _note(client, "already here")
    body = client.get("/entries/changes").json()
    assert body["ids"] == [] and body["more"] is False
    assert isinstance(body["since"], str) and body["since"]


def test_an_edit_after_the_stamp_comes_back_and_an_old_one_does_not(client, monkeypatch):
    from tessellate.api import routes_entries

    monkeypatch.setattr(routes_entries, "CHANGES_OVERLAP_SECONDS", 0.01)
    old = _note(client, "old note")
    edited = _note(client, "will change")
    time.sleep(0.03)
    stamp = client.get("/entries/changes").json()["since"]
    time.sleep(0.03)
    response = client.put(f"/entries/{edited['id']}", json={"content": "changed on the phone"})
    assert response.status_code == 200, response.text
    fresh = _note(client, "new on the phone")
    body = client.get("/entries/changes", params={"since": stamp}).json()
    assert set(body["ids"]) == {edited["id"], fresh["id"]}
    assert old["id"] not in body["ids"]
    time.sleep(0.05)
    again = client.get("/entries/changes", params={"since": body["since"]}).json()
    last = client.get("/entries/changes", params={"since": again["since"]}).json()
    assert last["ids"] == [], "past the overlap, a change is not sent for ever"


def test_the_stamp_overlaps_so_a_late_commit_is_asked_about_again(client):
    """Two seconds behind the newest change: the same id comes back with the
    same `updated_at` in `stamps`, which the client drops as already seen."""
    stamp = client.get("/entries/changes").json()["since"]
    note = _note(client, "late")
    first = client.get("/entries/changes", params={"since": stamp}).json()
    second = client.get("/entries/changes", params={"since": first["since"]}).json()
    assert note["id"] in second["ids"]
    assert second["stamps"][str(note["id"])] == first["stamps"][str(note["id"])]


def test_a_binned_note_is_a_change(client):
    gone = _note(client, "to bin")
    stamp = client.get("/entries/changes").json()["since"]
    time.sleep(0.02)
    client.delete(f"/entries/{gone['id']}")
    assert gone["id"] in client.get("/entries/changes", params={"since": stamp}).json()["ids"]


def test_boards_are_left_out(client):
    stamp = client.get("/entries/changes").json()["since"]
    time.sleep(0.02)
    board = client.post("/whiteboard/boards", json={"name": "A board"})
    assert board.status_code == 201, board.text
    note = _note(client, "a note")
    ids = client.get("/entries/changes", params={"since": stamp}).json()["ids"]
    assert note["id"] in ids
    assert board.json()["id"] not in ids


def test_a_bad_stamp_is_refused_plainly(client):
    response = client.get("/entries/changes", params={"since": "not a time"})
    assert response.status_code == 422


def test_more_than_the_cap_says_more(client, monkeypatch):
    from tessellate.api import routes_entries

    monkeypatch.setattr(routes_entries, "CHANGES_IDS_MAX", 2)
    stamp = client.get("/entries/changes").json()["since"]
    time.sleep(0.02)
    for n in range(3):
        _note(client, f"bulk {n}")
    body = client.get("/entries/changes", params={"since": stamp}).json()
    assert body["more"] is True and len(body["ids"]) == 2


def test_the_client_follows_changes_while_visible():
    """The client half, read from its source: polled while visible, at once
    when the tab comes back, and never over the note being edited (its save
    keeps the `base_hash` conflict prompt)."""
    source = (Path(__file__).resolve().parents[1] / "frontend/js/notes-list.js").read_text(encoding="utf-8")
    start = source.index("function followNoteChanges")
    body = source[start:start + 2500]
    assert "/entries/changes" in body
    assert "editingId" in body
    assert 'addEventListener("visibilitychange"' in source[start - 2000:start + 4000]


def test_the_client_slows_down_after_four_empty_answers_and_stops_hidden():
    """Battery (INBOX 1351): the ask is 15 s, 30 s after four empty answers,
    restored by a change or by the tab coming back, and not made while hidden."""
    source = (Path(__file__).resolve().parents[1] / "frontend/js/notes-list.js").read_text(encoding="utf-8")
    body = source[source.index("async function followNoteChanges") :][:3000]
    assert "if (document.hidden) return;" in body
    assert "noteChanges.quiet >= 4 ? 2 : 1" in body and "noteChanges.quiet = body.ids.length ? 0" in body
    assert "noteChanges.quiet = 0;" in body.split('addEventListener("visibilitychange"', 1)[1]
