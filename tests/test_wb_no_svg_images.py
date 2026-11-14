"""No SVG reaches a board as an image object (L-whiteboard-39 closed as moot by fact).

An SVG is markup that can run script, and `/media/` serves from the app's own origin, so it never
takes one. Each way a picture gets onto a board is checked here, so "there is no SVG image to
recolour" stays a fact and not a belief: the upload, the object validation, a template or library
item, the board paste (what an SVG re-import uses), the link fetch, the converters, and the
client paths that decide what is uploaded (source tests; the browser half is not run here).
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest

from tessellate.api import routes_files, wb_convert, wb_model
from tessellate.core import deps, security, webclip, webimage
from tests.test_webclip import FakeResponse, FakeSession

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
SVG = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect/></svg>'
SVG_URI = "data:image/svg+xml;base64," + base64.b64encode(SVG).decode()
BAD_URLS = [
    "/media/evil.svg", "/media/evil.SVG", "/media/evil.svgz", "/media/evil.html", "/media/noext",
    SVG_URI, "data:image/svg+xml,%3Csvg/%3E", "https://example.com/a.svg",
]


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    head = text[text.index(start):]
    return head[: head.index(end)]


# --- 1, 2: paste and drop upload first; the upload is the one door -------------------------------------------

@pytest.mark.parametrize("name", ["a.svg", "a.SVG", "a.svgz"])
def test_upload_refuses_an_svg_file_by_suffix(ai_client, name):
    got = ai_client.post("/media/upload", files={"file": (name, SVG, "image/svg+xml")}, data={"board": "true"})
    assert got.status_code == 415


@pytest.mark.parametrize("name", ["a.png", "a.jpg", "a.gif", "a.webp", "a.bmp", "a.ico", "a.avif"])
def test_upload_refuses_svg_markup_named_like_a_picture(ai_client, name):
    got = ai_client.post("/media/upload", files={"file": (name, SVG, "image/png")}, data={"board": "true"})
    assert got.status_code == 415


def test_the_upload_list_has_no_svg_and_the_object_rule_matches_it():
    assert ".svg" not in routes_files.MEDIA_SUFFIXES
    assert set(wb_model.MEDIA_PICTURE_SUFFIXES) == set(routes_files.MEDIA_SUFFIXES)


def test_a_stray_svg_in_the_media_folder_is_not_served(ai_client):
    folder = deps.get_config().data_dir / "media"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "planted.svg").write_bytes(SVG)
    got = ai_client.get("/media/planted.svg")
    assert got.status_code == 404


def test_paste_and_drop_place_only_what_the_upload_returned():
    src = _js("whiteboard.js")
    place = _between(src, "async function wbPlaceUploadedImage", "async function wbPlaceImageUrl")
    assert '"/media/upload"' in place and "wbPlaceImageUrl(uploaded.url" in place
    # A pasted data: picture becomes a File for that upload; it is never an object's address.
    assert "wbPlaceUploadedImage(new File(" in src
    # The one direct placement is an address already inside this notebook, and it is the only image object made here.
    assert 'if (local.startsWith("/media/")) return wbPlaceImageUrl(local, x, y);' in src
    assert src.count('wbCreateObject("image"') == 1 and 'wbCreateObject("image", { url }' in src


def test_no_client_image_object_is_made_from_a_data_or_outside_address():
    sites = []
    for path in sorted(JS.glob("whiteboard*.js")):
        sites += re.findall(r'wbCreateObject\("image", \{ url[^}]*\}', path.read_text(encoding="utf-8"))
    assert sites, "the placement sites moved: update this test"
    assert not [s for s in sites if re.search(r"data:|blob:|http", s)]


# --- 3: an image object whose address is an SVG --------------------------------------------------------------

@pytest.mark.parametrize("url", BAD_URLS)
def test_an_image_object_with_an_svg_address_is_refused(ai_client, url):
    made = ai_client.post("/whiteboard/objects", json={"kind": "image", "data": {"url": url}})
    assert made.status_code == 422


def test_an_existing_image_object_cannot_be_pointed_at_an_svg(ai_client):
    made = ai_client.post("/whiteboard/objects", json={"kind": "image", "data": {"url": "/media/ok.png"}})
    assert made.status_code == 201, made.text
    got = ai_client.put(f"/whiteboard/objects/{made.json()['id']}", json={"kind": "image", "data": {"url": "/media/evil.svg"}})
    assert got.status_code == 422


@pytest.mark.parametrize("name", ["/media/a.png", "/media/a.jpg", "/media/a.pdf", "/media/0123abcd.webp"])
def test_the_picture_suffixes_still_pass(name):
    assert wb_model.MEDIA_URL_RE.match(name)


def test_the_topic_picture_refuses_an_svg_address(ai_client):
    made = ai_client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "x", "image": "/media/evil.svg"}})
    assert made.status_code == 422


@pytest.mark.parametrize("url,code", [("/media/evil.svg", 422), ("/media/fill.png", 200)])
def test_a_picture_fill_refuses_an_svg_address(ai_client, url, code):
    data = json.dumps({"d": "M 0 0 L 10 0 L 10 10 Z", "shape": "rect", "color": "#123456", "width": 2, "fill_image": url})
    got = ai_client.post("/whiteboard/sketches", json={"data": data})
    assert got.status_code == code


# --- 4: draw.io import ---------------------------------------------------------------------------------------

def test_drawio_import_draws_an_svg_picture_to_a_png_before_the_upload():
    src = _js("whiteboard-interchange.js")
    pic = _between(src, "async picture({ mime, base64 }", "async svgToPng")
    assert pic.index('mime === "image/svg+xml"') < pic.index('"/media/upload"')
    assert "svgToPng(file, box)" in pic and "if (!file) return null;" in pic
    # The upload's name comes from the converted blob's type, which the canvas made a PNG.
    assert "file.type.slice(6)" in pic
    assert 'canvas.toBlob(done, "image/png")' in src


def test_drawio_import_keeps_only_a_media_address_or_an_inline_picture():
    src = _js("whiteboard-interchange.js")
    assert r"/^\/media\/[A-Za-z0-9][A-Za-z0-9._-]*$/.test(s.image" in src
    assert "an outside address would make the board call out" in src
    # An address the client kept still meets the server's suffix rule when the object is made (see test 3).


# --- 5: Miro, GraphML, PlantUML, EMF -------------------------------------------------------------------------

def test_miro_images_are_counted_and_not_placed(ai_client):
    box = {"position": {"x": 0, "y": 0}, "geometry": {"width": 100, "height": 60}}
    board = {"data": [
        {"id": "1", "type": "shape", "data": {"content": "A", "shape": "rectangle"}, **box},
        {"id": "2", "type": "image", "data": {"imageUrl": "https://x.example/a.svg"}, **box},
        {"id": "3", "type": "image", "data": {"imageUrl": SVG_URI}, **box},
    ]}
    out = ai_client.post("/whiteboard/convert", json={"format": "miro", "content": json.dumps(board)})
    assert out.status_code == 200, out.text
    graph = out.json()["graph"]
    assert graph["skipped"] == 2 and len(graph["nodes"]) == 1
    assert "svg" not in json.dumps(out.json()).lower()


def test_graphml_never_returns_a_picture_address(ai_client):
    graphml = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><graph edgedefault="directed">'
        f'<node id="a"><data key="d0">{SVG_URI}</data></node><node id="b"/><edge source="a" target="b"/></graph></graphml>'
    )
    got = ai_client.post("/whiteboard/convert", json={"format": "graphml", "content": graphml})
    assert got.status_code == 200 and "data:image" not in json.dumps(got.json())


def test_the_converters_never_name_an_image_kind_or_an_svg_type():
    src = Path(wb_convert.__file__).read_text(encoding="utf-8")
    assert not re.search(r'"(kind|type)":\s*"image"', src) and "svg+xml" not in src


def test_an_emf_is_said_not_placed(ai_client):
    assert "was not placed as a picture" in Path(wb_convert.__file__).read_text(encoding="utf-8")
    got = ai_client.post("/whiteboard/convert", json={"format": "emf", "data_b64": base64.b64encode(b"not an emf").decode()})
    assert got.status_code == 422


# --- 6: a library item or a template -------------------------------------------------------------------------

def _element(url):
    return {"box": {"w": 1, "h": 1}, "items": [{"key": "p", "kind": "object", "type": "image", "data": {"url": url}, "x": 0, "y": 0, "w": 20, "h": 20}]}


@pytest.mark.parametrize("url", BAD_URLS)
def test_a_library_item_refuses_an_svg_picture(ai_client, url):
    got = ai_client.post("/board-library", json={"kind": "element", "name": "Svg", "payload": _element(url)})
    assert got.status_code == 422


def test_no_built_in_library_or_template_holds_an_svg_picture():
    hits = []
    for path in (ROOT / "frontend" / "board-library").rglob("*"):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if path.suffix == ".svg" or b"svg+xml" in raw or re.search(rb'"(type|kind)":\s*"image"', raw):
            hits.append(path.name)
    assert hits == []


# --- 7: an image by URL (the map topic's insert from link) ---------------------------------------------------

@pytest.fixture
def net(monkeypatch):
    pages: dict[str, FakeResponse] = {}
    monkeypatch.setattr(security, "_resolve", lambda host: ["93.184.216.34"])
    monkeypatch.setattr(webclip, "_new_session", lambda: FakeSession(pages, []))
    return pages


@pytest.mark.parametrize("kind,body", [("image/svg+xml", SVG), ("image/png", SVG)])
def test_a_link_to_an_svg_is_refused_by_type_and_by_bytes(net, kind, body):
    net["pics.example"] = FakeResponse(200, body, {"content-type": kind})
    with pytest.raises(webclip.ClipRefused):
        webimage.fetch_image("https://pics.example/a.svg")


def test_the_link_fetch_keeps_no_svg_suffix():
    assert "image/svg+xml" not in webimage._SUFFIX and ".svg" not in webimage._SUFFIX.values()


# --- 8: the board's own SVG coming back in -------------------------------------------------------------------

def test_the_svg_reimport_makes_rows_only_through_the_validated_copy_route():
    src = _js("whiteboard-interchange.js")
    body = _between(src, "async function wbImportBoardRows", "//: A Mermaid flowchart")
    assert "wbCreateCopies(" in body and "<image" not in body and "data:image" not in body
    reader = _between(src, "function wbBoardRowsFromSvg", "//: The rows of what an export covers")
    assert "JSON.parse(body)" in reader and "innerHTML" not in reader


@pytest.mark.parametrize("url", BAD_URLS)
def test_a_pasted_or_reimported_image_row_with_an_svg_address_is_refused(ai_client, url):
    item = {"key": "k", "object": {"kind": "image", "data": {"url": url}, "x": 0, "y": 0, "width": 50, "height": 50}}
    got = ai_client.post("/whiteboard/boards/0/paste", json={"items": [item]})
    assert got.status_code == 422
    state = ai_client.get("/whiteboard/").json()
    assert state["objects"] == []


def test_an_export_inlines_pictures_for_the_file_only():
    src = _js("whiteboard.js")
    assert '.filter((u) => !u.startsWith("data:"))' in _between(src, "async function wbInlineSvgImages", "async function wbRasterizeSvg")


# --- 9: anything else ----------------------------------------------------------------------------------------

def test_the_one_svg_drawn_on_a_board_is_the_diagram_object_made_from_mermaid_source():
    src = _js("whiteboard-interchange.js")
    assert "data:image/svg+xml;charset=utf-8,${encodeURIComponent(known.svg)}" in _between(src, "function wbDiagramDataUrl", "function wbBuildDiagram")


@pytest.mark.parametrize("name", ["whiteboard-effects.js", "whiteboard-format.js", "whiteboard-map.js", "whiteboard-pdf.js"])
def test_every_other_picture_uploader_goes_through_the_upload_route(name):
    assert '"/media/upload"' in _js(name)
