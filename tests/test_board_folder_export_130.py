"""L-world-class-130 (WORLD_CLASS_PLAN decision 66): a board or map exports
as a folder: its picture as SVG and PNG with the notes it links as Markdown,
one zip. The document's PDF is the print path documents-export.js already
has (Print or save as PDF), so only the board half was missing."""

from __future__ import annotations

import base64
import io
import zipfile

from tests._app_js import frontend_text

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'


def _note(client, text, category=None):
    body = {"content": text}
    if category:
        body["category"] = category
    return client.post("/entries", json=body).json()


def test_the_folder_holds_the_picture_and_the_linked_notes(client):
    a = _note(client, "Launch checklist", category="Work")
    b = _note(client, "Venue options", category="Work")
    _note(client, "Not on the board")
    r = client.post("/export/board-folder", json={"name": "Launch plan", "svg": SVG, "png": PNG, "ids": [a["id"], b["id"]]})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert 'filename="launch-plan.zip"' in r.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "launch-plan/launch-plan.svg" in names and "launch-plan/launch-plan.png" in names
    notes = [n for n in names if n.startswith("launch-plan/notes/") and n.endswith(".md")]
    assert len(notes) == 2, names
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert zf.read("launch-plan/launch-plan.svg").decode() == SVG
    assert zf.read("launch-plan/launch-plan.png").startswith(b"\x89PNG")
    assert any("Launch checklist" in zf.read(n).decode() for n in notes)


def test_a_board_with_no_notes_is_still_a_folder(client):
    r = client.post("/export/board-folder", json={"name": "", "svg": SVG, "ids": []})
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert names == ["board/board.svg"]


def test_bad_input_is_refused(client):
    r0 = client.post("/export/board-folder", json={"name": "x", "svg": "<p>not svg</p>", "ids": []})
    assert r0.status_code == 422
    r1 = client.post("/export/board-folder", json={"name": "x", "svg": SVG, "png": "!!notbase64", "ids": []})
    assert r1.status_code == 422
    r2 = client.post("/export/board-folder", json={"name": "x", "svg": SVG, "png": base64.b64encode(b"GIF89a").decode(), "ids": []})
    assert r2.status_code == 422


def test_the_export_dialog_offers_it():
    js = frontend_text("whiteboard.js")
    start = js.index("const WB_EXPORT_FORMATS = [")
    table = js[start : js.index("\n];\n", start)]
    assert 'value: "folder", label: "Folder with notes"' in table
    assert '"/export/board-folder"' in table
