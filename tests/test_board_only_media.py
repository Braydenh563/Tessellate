"""K18: a picture placed on a board or map stays on the board.

Asked for (owner-1026b K18): no Library entry, no caption or reading job, no
agent corner tab, until the person chooses Save to Library.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from tessellate.ai import captioning, vision_ocr
from tessellate.core import ocr
from tessellate.core.database import MediaUpload

PNG = b"\x89PNG\r\n\x1a\n"


def _readers(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ocr, "extract_in_background", lambda *a: calls.append("ocr"))
    monkeypatch.setattr(captioning, "caption_in_background", lambda *a: calls.append("caption"))
    monkeypatch.setattr(vision_ocr, "vision_ocr_in_background", lambda *a: calls.append("vision"))
    return calls


def _board_upload(client):
    return client.post(
        "/media/upload", data={"board": "true"}, files={"file": ("shot.png", PNG, "image/png")}
    ).json()


def test_a_board_upload_is_marked_and_a_plain_one_is_not(ai_client):
    board = _board_upload(ai_client)
    plain = ai_client.post("/media/upload", files={"file": ("b.png", PNG, "image/png")}).json()
    marked = ai_client.get(f"/media/meta/{board['url'].rsplit('/', 1)[1]}").json()
    unmarked = ai_client.get(f"/media/meta/{plain['url'].rsplit('/', 1)[1]}").json()
    assert marked["board_only"] is True and unmarked["board_only"] is False


def test_the_library_listing_leaves_board_pictures_out(ai_client):
    board = _board_upload(ai_client)
    plain = ai_client.post("/media/upload", files={"file": ("b.png", PNG, "image/png")}).json()
    listed = ai_client.get("/media")
    assert [row["id"] for row in listed.json()] == [plain["id"]]
    assert listed.headers["X-Total-Count"] == "1"
    assert board["id"] not in [row["id"] for row in listed.json()]


def test_placing_a_board_picture_starts_no_reader(ai_client, monkeypatch):
    calls = _readers(monkeypatch)
    board = _board_upload(ai_client)
    ai_client.post("/whiteboard/objects", json={"kind": "image", "data": {"url": board["url"]}, "board_id": None})
    assert calls == []


def test_a_plain_upload_placed_on_a_board_still_starts_its_readers(ai_client, monkeypatch):
    calls = _readers(monkeypatch)
    plain = ai_client.post("/media/upload", files={"file": ("b.png", PNG, "image/png")}).json()
    ai_client.post("/whiteboard/objects", json={"kind": "image", "data": {"url": plain["url"]}, "board_id": None})
    assert "ocr" in calls or "caption" in calls


def test_save_to_library_lists_it_and_starts_the_readers(ai_client, monkeypatch):
    calls = _readers(monkeypatch)
    board = _board_upload(ai_client)
    saved = ai_client.post(f"/media/{board['id']}/library")
    listed = ai_client.get("/media").json()
    assert saved.status_code == 200 and saved.json()["board_only"] is False
    assert board["id"] in [row["id"] for row in listed]
    assert "ocr" in calls or "caption" in calls


def test_save_to_library_is_idempotent_and_404s_on_nothing(ai_client):
    board = _board_upload(ai_client)
    first = ai_client.post(f"/media/{board['id']}/library")
    second = ai_client.post(f"/media/{board['id']}/library")
    missing = ai_client.post("/media/99999/library")
    assert (first.status_code, second.status_code, missing.status_code) == (200, 200, 404)


def test_board_pictures_stay_out_of_search_and_the_ai_file_list(ai_client, session):
    board = _board_upload(ai_client)
    row = session.get(MediaUpload, board["id"])
    row.caption = "a red bicycle"
    session.commit()
    from tessellate.ai.tools import files as file_tools

    found = file_tools._search_files(session, {"query": "bicycle"})
    assert "shot.png" not in str(found)


def test_a_board_picture_is_not_a_search_hit_until_saved(ai_client):
    board = _board_upload(ai_client)
    before = ai_client.get("/search", params={"q": "shot"}).text
    ai_client.post(f"/media/{board['id']}/library")
    after = ai_client.get("/search", params={"q": "shot"}).text
    assert "shot.png" not in before and "shot.png" in after


# The frontend half --------------------------------------------------------

from pathlib import Path  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_JS = _ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return frontend_text(name) if name.startswith("whiteboard") else (_JS / name).read_text(encoding="utf-8")


def test_every_board_picture_upload_says_it_is_board_only():
    placed = _js("whiteboard.js")
    at = placed.index("async function wbPlaceUploadedImage(")
    assert 'formData.append("board", "true")' in placed[at : at + 900]
    bg = placed[placed.index("const file = bgImageInput.files?.[0];") :][:500]
    assert 'formData.append("board", "true")' in bg
    assert 'formData.append("board", "true")' in _js("whiteboard-map.js")
    assert 'body.append("board", "true")' in _js("whiteboard-format.js")
    #: A board export is a finished picture, filed on purpose: it stays `direct`.
    assert 'formData.append("direct", "true")' in placed


def test_the_format_panel_saves_to_the_library_and_toggles_captions():
    html = (_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="wb-fmt-tolibrary"' in html and 'id="wb-fmt-showcaption"' in html
    fmt = _js("whiteboard-format.js")
    assert "`/media/${meta.id}/library`" in fmt and 'prefs.set("wb-show-captions"' in fmt
    #: Off until asked for, and drawn after every render.
    assert 'prefs.get("wb-show-captions", null) === "1"' in fmt
    assert 'if (typeof wbFmtState !== "undefined") wbFmtState.paintCaptions?.();' in _js("whiteboard.js")
    #: A map topic that carries a picture gets its caption too.
    assert "WB_MAP_KINDS.has(o.kind) ? o.data?.image" in fmt


def test_help_names_where_a_board_picture_lives():
    from tessellate.ai.help_topics_core import HELP_TOPICS

    body = next(t["body"] for t in HELP_TOPICS if t["id"] == "files-images")
    assert "Save to Library" in body and "Captions" in body
    html = (_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "<b>Save to Library</b>" in html
    #: K18 left line: the caption shows under a note's pictures too, and the help says so.
    assert "popup" in body and "attached" in body
    assert "popup's menu has the same switch" in html


def test_a_notes_own_pictures_get_the_caption_line_in_the_popup_and_the_timeline_view():
    layout = _js("image-layout.js")
    #: One cached lookup per picture, drawn as text (never markup), under the muted token, pref-gated.
    assert "imageLayout.caption = function" in layout and "imageLayout.paintCaptions = function" in layout
    body = layout[layout.index("imageLayout.caption = function") : layout.index("imageLayout.paintCaptions = function")]
    assert "/media/meta/" in body and "imageLayout.captions" in body
    assert "textContent" in body and "innerHTML" not in body
    assert 'prefs.get("wb-show-captions", null) === "1"' in body
    assert "/files/" not in body
    #: A graph popup's live picture and the timeline's note view call it; the popup menu toggles the pref.
    assert 'closest?.("#graph-popup")' in _js("documents-cm.js")
    assert "imageEditTarget(img) && imageLayout.caption(" in layout
    graph = _js("graph.js")
    assert "Show picture captions" in graph and "Hide picture captions" in graph
    assert 'prefs.set("wb-show-captions"' in graph
    css = (_ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    block = css[css.index(".md-picture-caption {") :][:500]
    assert "color: var(--muted)" in block and "var(--text-xs)" in block
    #: The Format panel's Library and Captions buttons each take a row: two in one row wrapped.
    html = (_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    row = html[html.index('<span class="wb-fmt-label">Library</span>') :]
    assert row.index('id="wb-fmt-tolibrary"') < row.index("</div>") < row.index('id="wb-fmt-showcaption"')
