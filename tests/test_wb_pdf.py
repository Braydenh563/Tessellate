"""A PDF on a board (L-whiteboard-2): placed as one picture per page, or kept as one object that opens the file.

The browser half is `scratchpad/ui-sweeps/wbpdf.js` (13 checks on a real PDF); this holds the wiring and the server's rules.
"""

from __future__ import annotations

import re

from pathlib import Path

from tests._app_js import frontend_text

PAGE = "/media/pdf-page/0123abcd.pdf/0"


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "PDF board", "type": "board"}).json()


def _object(client, board, kind, data):
    body = {"kind": kind, "data": data, "board_id": board["id"], "x": 0, "y": 0, "z": 1, "width": 320, "height": 450}
    return client.post("/whiteboard/objects", json=body)


def test_a_pdf_page_picture_and_its_file_are_kept(ai_client):
    board = _board(ai_client)
    made = _object(ai_client, board, "image", {"url": PAGE, "pdf": "/media/0123abcd.pdf", "pdf_name": "plan.pdf"})
    assert made.status_code == 201, made.text
    assert made.json()["data"]["pdf"] == "/media/0123abcd.pdf"


def test_a_card_for_a_pdf_that_cannot_be_drawn_keeps_its_file(ai_client):
    board = _board(ai_client)
    made = _object(ai_client, board, "text", {"content": "plan.pdf", "pdf": "/media/0123abcd.pdf"})
    assert made.status_code == 201, made.text


def test_an_image_still_has_to_be_a_media_file_or_a_pdf_page(ai_client):
    board = _board(ai_client)
    for url in ("https://example.com/a.png", "/media/pdf-page/../x.pdf/0", "/media/pdf-page/a.png/0", "/media/pdf-page/a.pdf/x"):
        assert _object(ai_client, board, "image", {"url": url}).status_code == 422, url


def test_the_pdf_link_is_held_to_a_media_pdf(ai_client):
    board = _board(ai_client)
    for bad in ("https://example.com/a.pdf", "/media/../a.pdf", "/media/a.png", "javascript:1"):
        assert _object(ai_client, board, "image", {"url": PAGE, "pdf": bad}).status_code == 422, bad


def test_the_board_hands_a_pdf_to_the_pdf_module_and_loads_it():
    app = frontend_text("whiteboard.js")
    assert "wbFmtState.pdf?.isPdf(file)" in app and "wbFmtState.pdf.place(file, x, y)" in app
    assert "whiteboard-pdf.js" in frontend_text("lazy-entries.js")
    assert "application/pdf" in (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_pdf_module_asks_once_caps_pages_and_is_one_undo_step():
    js = frontend_text("whiteboard-pdf.js")
    assert 'confirmLabel: "Place as pages"' in js and 'cancelLabel: "Attach as one object"' in js
    assert "const MAX_PAGES = 20;" in js
    assert re.search(r"wbRecordGesture\(async \(\) => \{\s*if \(choice\)", js)
    assert "Object.assign(wbFmtState, { pdf:" in js
