"""L-world-class-130 (WORLD_CLASS_PLAN decision 66): a board or map exports
as a folder: its picture as SVG and PNG with the notes it links as Markdown,
one zip. The document's PDF is the print path documents-export.js already
has (Print or save as PDF), so only the board half was missing."""

from __future__ import annotations

import io
import zipfile

from tests._app_js import frontend_text

PNG = b"\x89PNG\r\n\x1a\nfake"
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'


def _post(client, name, svg, ids, png=None):
    """Multipart, as the browser sends it: an upload keeps the large body cap,
    where a JSON body past 16 MB is refused before the route reads it."""
    files = {"svg": ("board.svg", svg.encode() if isinstance(svg, str) else svg, "image/svg+xml")}
    if png is not None:
        files["png"] = ("board.png", png, "image/png")
    return client.post("/export/board-folder", data={"name": name, "ids": ",".join(map(str, ids))}, files=files)


def _note(client, text, category=None):
    body = {"content": text}
    if category:
        body["category"] = category
    return client.post("/entries", json=body).json()


def test_the_folder_holds_the_picture_and_the_linked_notes(client):
    a = _note(client, "Launch checklist", category="Work")
    b = _note(client, "Venue options", category="Work")
    _note(client, "Not on the board")
    r = _post(client, "Launch plan", SVG, [a["id"], b["id"]], png=PNG)
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
    r = _post(client, "", SVG, [])
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert names == ["board/board.svg"]


def test_bad_input_is_refused(client):
    assert _post(client, "x", "<p>not svg</p>", []).status_code == 422
    assert _post(client, "x", SVG, [], png=b"GIF89a").status_code == 422
    assert _post(client, "x", SVG, ["a"]).status_code == 422


def test_a_board_past_the_json_cap_still_exports(client):
    """Review 5907752577: a board with pictures inlined passes 16 MB; sent as
    JSON it met a 413 and the browser saved the error as the zip."""
    big = SVG.replace("></svg>", ">" + "<!--" + "x" * (18 * 1024 * 1024) + "--></svg>")
    r = _post(client, "Big", big, [], png=PNG)
    assert r.status_code == 200, r.status_code
    assert "big/big.png" in zipfile.ZipFile(io.BytesIO(r.content)).namelist()


def test_the_browser_sends_form_data():
    js = frontend_text("whiteboard.js")
    start = js.index("async function wbExportBoardFolder(")
    body = js[start : js.index("\n    },\n", start)]
    assert "new FormData()" in body and "JSON.stringify" not in body
    #: `api()` throws on a refusal, so an error is never saved as the zip.
    assert 'api("/export/board-folder"' in body


def test_the_export_dialog_offers_it():
    js = frontend_text("whiteboard.js")
    start = js.index("const WB_EXPORT_FORMATS = [")
    table = js[start : js.index("\n];\n", start)]
    assert 'value: "folder", label: "Folder with notes"' in table
    assert '"/export/board-folder"' in table


def test_a_large_board_is_built_on_disk_not_in_memory(tmp_path):
    """Review 6008796874, finding 7: the uploads, the zip and the response were
    each held whole, over 300 MB at the cap. Now the uploads are copied in
    1 MB chunks into a zip that spills to disk past 4 MB. Measured with a
    24 MB PNG: the old path peaked above 48 MB (the bytes plus the zip)."""
    import os
    import tracemalloc

    from tessellate.api.routes_settings_transfer import _stream_and_close, build_board_folder

    png_path = tmp_path / "board.png"
    with png_path.open("wb") as out:
        out.write(b"\x89PNG\r\n\x1a\n")
        for _ in range(24):
            out.write(os.urandom(1024 * 1024))
    svg = io.BytesIO(SVG.encode())
    with png_path.open("rb") as png:
        tracemalloc.start()
        try:
            spool = build_board_folder(svg, png, "big", None)
            size = sum(len(chunk) for chunk in _stream_and_close(spool))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    assert size > 24 * 1024 * 1024
    assert peak < 8 * 1024 * 1024, f"peak {peak / 1e6:.1f} MB"


def test_a_picture_past_the_cap_is_refused(client, monkeypatch):
    from tessellate.api import routes_settings_transfer as transfer

    monkeypatch.setattr(transfer, "BOARD_PNG_MAX", 16)
    assert _post(client, "x", SVG, [], png=PNG + b"x" * 32).status_code == 413
    assert _post(client, "x", "<svg>\xff</svg>".encode("latin-1"), []).status_code == 422
