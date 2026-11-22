"""WORLD_CLASS_PLAN 27.1, the Spaces row and the Notes row's templates
(L-world-class-22): moving a note between spaces with its links kept, a
space's own export, a space's own dashboard line, and template variables.

Before: a note moved to another space took along only the links whose both
ends moved, so a link to a note left behind vanished from both spaces (it
showed only under All spaces) and nothing said so; a space could be exported
only by switching to it and finding Settings, Import & export, whose file was
called the notebook; the dashboard never said which space it was counting;
and a note template knew the date, the time, the clipboard and the caret.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _note(client, text, space=None):
    headers = {"X-Workspace-ID": space} if space else {}
    return client.post("/entries", json={"content": text}, headers=headers).json()


def _links(client, entry_id, space):
    return client.get(f"/entries/{entry_id}", headers={"X-Workspace-ID": space}).json()["links"]


# --- moving with its links kept ----------------------------------------------


def test_a_move_names_the_linked_notes_it_left_behind(client):
    a = _note(client, "Alpha note about trains")
    b = _note(client, "Beta note about stations")
    c = _note(client, "Gamma note, linked to nothing")
    linked = client.post(f"/entries/{b['id']}/links", json={"target_id": a["id"]})
    assert linked.status_code == 200

    moved = client.post("/spaces/work/move-notes", json={"ids": [a["id"]]}).json()
    assert moved["moved"] == 1
    #: Either direction counts: b links to a, so a's move leaves b's link out of view.
    assert moved["linked"] == [b["id"]]
    assert c["id"] not in moved["linked"]
    assert _links(client, a["id"], "work") == []


def test_bringing_the_linked_notes_too_puts_the_link_back_in_view(client):
    a = _note(client, "Alpha note about trains")
    b = _note(client, "Beta note about stations")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    first = client.post("/spaces/work/move-notes", json={"ids": [a["id"]]}).json()
    second = client.post("/spaces/work/move-notes", json={"ids": first["linked"]}).json()
    assert second["moved"] == 1 and second["linked"] == []
    assert [link["entry_id"] for link in _links(client, a["id"], "work")] == [b["id"]]


def test_a_move_of_both_ends_names_nothing(client):
    a = _note(client, "Alpha note about trains")
    b = _note(client, "Beta note about stations")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    moved = client.post("/spaces/work/move-notes", json={"ids": [a["id"], b["id"]]}).json()
    assert moved["linked"] == []
    assert len(_links(client, a["id"], "work")) == 1


def test_the_move_offers_to_bring_the_linked_notes():
    body = app_js_text().split("async function moveNotesToSpace(", 1)[1].split("\n}\n", 1)[0]
    assert "moved.linked" in body
    assert "Bring them too" in body
    #: One Undo for both moves: the second move's `from` joins the first's.
    assert body.index("Bring them too") < body.index("pushUndo(")


# --- a space's own export ----------------------------------------------------


def test_the_space_menu_exports_every_space():
    menu = app_js_text().split("function spaceMenuOption(", 1)[1].split("\n}\n", 1)[0]
    assert "Export ${name}" in menu
    #: Not only the deletable ones: the default space is a space too.
    assert menu.index("Export ${name}") < menu.index("if (deletable)")
    lazy = (JS / "batch-space.js").read_text(encoding="utf-8")
    body = lazy.split("async function exportSpace(", 1)[1].split("\n}\n", 1)[0]
    assert '"/export/folder"' in body and '"X-Workspace-ID": id' in body


def test_a_space_export_carries_only_that_space(client):
    import io
    import zipfile

    _note(client, "Kept in the default space")
    _note(client, "Kept in the work space", space="work")
    response = client.get("/export/folder", headers={"X-Workspace-ID": "work"})
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        text = " ".join(archive.read(n).decode("utf-8", "ignore") for n in archive.namelist() if n.endswith(".md"))
    assert "Kept in the work space" in text and "Kept in the default space" not in text


# --- a space's own dashboard line ----------------------------------------------


def test_the_dashboard_line_names_the_space_it_counts():
    dash = (JS / "dashboard.js").read_text(encoding="utf-8")
    body = dash.split("async function renderDashSubmessage(", 1)[1].split("\n}\n", 1)[0]
    assert '"space"' in body and "In ${" in body
    assert "SPACE_ALL" in body
