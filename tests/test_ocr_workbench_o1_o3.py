"""The OCR workbench's speed (attach-1026 O1, O2, O3).

The owner, 2026-10-26: "clicking between the ocr workbench left sidebar
headers for files and pages like going between files really quick and viweing
the pages and the pages loading and the page number in the top pill updating
is slow and laggy"; "I think it waits for rapid ocr or tesserract to read the
whole ndocument first before loading the other pages"; "rendering the regions
on pdfs is a little flashy and on and off".

Measured before (`scratchpad/ocr/ocrspeed.js`, a 24-page PDF, 1440): the pill
read "Page 4 of 24" 3110 ms after the click, with the picture there at 10 ms,
because the pill, the page rail and the mode all waited on the regions answer,
and that answer waited on the server's one PDF lock behind 24 full-size rail
thumbnails, each a 456 ms render (`optimize=True` was 340 ms of it). Twelve
boxes and 48 live words were removed and re-added on every reload of an
unchanged page.

What these hold:

- the server keeps the pages it rendered, draws a rail thumbnail at a quarter
  of the size, and does not spend a second on PNG recompression for a viewer;
- the pill and the active rail item move in the same frame as the click, the
  page count comes from the cheap `pdf-info` and is remembered per file, and a
  stale answer (another page, another file) neither paints nor holds the next
  one up: the previous regions request is aborted;
- the box and live-word overlays keep the nodes of regions that did not change.
"""

from __future__ import annotations

import io
import re
import struct
from pathlib import Path

import pytest

from tessellate.core import pdfpages
from tests.test_pdfpages import ONE_PAGE_PDF

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
PDFPAGES_SRC = (ROOT / "src" / "tessellate" / "core" / "pdfpages.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "src" / "tessellate" / "api" / "routes_files.py").read_text(encoding="utf-8")

needs_pdfium = pytest.mark.skipif(
    not pdfpages.available(), reason="the pdfpages extra is not installed"
)


def _body(source: str, name: str) -> str:
    match = re.search(rf"(?:async )?function {name}\(", source)
    assert match, name
    depth, i = 0, source.index(") {", match.end()) + 2
    start = i
    while True:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1


def _code(text: str) -> str:
    """A body with its `//` comment lines and trailing comments taken out."""
    return "\n".join(re.sub(r"\s//.*$", "", line) for line in text.splitlines() if not line.lstrip().startswith("//"))


def _png_width(png: bytes) -> int:
    return struct.unpack(">I", png[16:20])[0]


@pytest.fixture()
def one_page(tmp_path) -> Path:
    path = tmp_path / "scan.pdf"
    path.write_bytes(ONE_PAGE_PDF)
    return path


# --- the server: keep what was drawn, draw less, recompress nothing --------------


def test_the_page_cache_evicts_the_oldest_when_it_is_over_its_budget(monkeypatch):
    monkeypatch.setattr(pdfpages, "_CACHE_BYTES", 10)
    pdfpages._cache_clear()
    pdfpages._cache_put(("a",), b"123456")
    pdfpages._cache_put(("b",), b"1234")
    assert pdfpages._cache_get(("a",)) == b"123456"  # a is now the newest
    pdfpages._cache_put(("c",), b"123")
    assert pdfpages._cache_get(("b",)) is None, "the least recently used goes first"
    assert pdfpages._cache_get(("a",)) == b"123456"
    assert pdfpages._cache_get(("c",)) == b"123"
    pdfpages._cache_put(("big",), b"x" * 11)
    assert pdfpages._cache_get(("big",)) is None, "one answer over the whole budget is not kept"
    pdfpages._cache_clear()


@needs_pdfium
def test_a_page_drawn_twice_is_rendered_once(one_page, monkeypatch):
    pdfpages._cache_clear()
    calls: list[int] = []
    real = pdfpages._render_one

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(pdfpages, "_render_one", counting)
    first = pdfpages.render_page(one_page, 0)
    second = pdfpages.render_page(one_page, 0)
    assert first == second and first
    assert len(calls) == 1
    thumb = pdfpages.render_page(one_page, 0, thumb=True)
    assert thumb and thumb != first
    assert len(calls) == 2, "a thumbnail is its own picture"
    pdfpages.render_page(one_page, 0, thumb=True)
    assert len(calls) == 2


@needs_pdfium
def test_a_changed_file_is_drawn_again(one_page):
    pdfpages._cache_clear()
    before = pdfpages.render_page(one_page, 0)
    one_page.write_bytes(ONE_PAGE_PDF.replace(b"[0 0 200 100]", b"[0 0 300 150]"))
    after = pdfpages.render_page(one_page, 0)
    assert _png_width(after) != _png_width(before)


@needs_pdfium
def test_a_thumbnail_is_a_quarter_of_the_width(one_page):
    full = pdfpages.render_page(one_page, 0)
    thumb = pdfpages.render_page(one_page, 0, thumb=True)
    assert _png_width(thumb) * 4 == pytest.approx(_png_width(full), abs=4)


def test_pages_are_not_recompressed():
    """`optimize=True` cost 340 ms of a 456 ms page for 3% fewer bytes, held
    under the one PDF lock that every other page waits for."""
    saves = re.findall(r"image\.save\(buffer[^)]*\)", PDFPAGES_SRC)
    assert saves and all("optimize" not in save for save in saves)


THREE_PAGE_PDF = ONE_PAGE_PDF.replace(b"/Kids[3 0 R]/Count 1", b"/Kids[3 0 R 3 0 R 3 0 R]/Count 3")


@needs_pdfium
def test_a_whole_document_batch_lets_the_lock_go_between_pages(tmp_path, monkeypatch):
    """The model's batch held the lock for all eight pages (~3.6 s), and a page
    view or a thumbnail waited behind the lot: the owner's "waits for the whole
    document first"."""
    path = tmp_path / "three.pdf"
    path.write_bytes(THREE_PAGE_PDF)
    assert pdfpages.page_count(path) == 3
    held_between: list[bool] = []

    class Clock:
        @staticmethod
        def sleep(_seconds):
            held_between.append(pdfpages._pdfium_lock.locked())

    monkeypatch.setattr(pdfpages, "time", Clock)
    assert len(pdfpages.render_pages(path)) == 3
    assert held_between == [False, False, False], "the lock is free between pages"


@needs_pdfium
def test_the_route_serves_a_thumbnail_on_request(client):
    created = client.post(
        "/media/upload",
        files={"file": ("deck.pdf", io.BytesIO(ONE_PAGE_PDF), "application/pdf")},
    )
    assert created.status_code == 200, created.text
    name = created.json()["url"].rsplit("/", 1)[-1]
    full = client.get(f"/media/pdf-page/{name}/0")
    thumb = client.get(f"/media/pdf-page/{name}/0?thumb=1")
    assert full.status_code == thumb.status_code == 200
    assert _png_width(thumb.content) < _png_width(full.content)
    assert thumb.headers["cache-control"].startswith("private")


def test_both_page_routes_take_the_thumb_flag():
    assert len(re.findall(r"thumb: bool = False", ROUTES)) >= 2
    assert len(re.findall(r"pdfpages\.render_page\(path, index, thumb=thumb\)", ROUTES)) == 2


# --- O1: the pill and the rail move at once ----------------------------------------


def test_the_pill_is_set_before_anything_is_awaited():
    body = _code(_body(LIBRARY, "ocrLoadPage"))
    first_await = body.index("await ")
    assert "ocrSyncPager(image, true)" in body[:first_await], "the page label waited on the network"
    assert "ocrRailActive(" in body[:first_await], "the rail's lit item waited on the network"


def test_the_page_count_does_not_wait_for_the_regions():
    body = _code(_body(LIBRARY, "ocrLoadPage"))
    assert "ocrKnownPages(image" in body
    assert body.index("ocrKnownPages(image") < body.index("ocrRegionsUrl(image"), (
        "the count (and so the pill, the rail and the layout mode) is asked for first"
    )
    known = _code(_body(LIBRARY, "ocrKnownPages"))
    assert "pdf-info" in known and "ocrPageCounts" in known


def test_a_stale_load_is_aborted_and_cannot_paint():
    body = _code(_body(LIBRARY, "ocrLoadPage"))
    assert "ocrLoadAbort?.abort()" in body
    assert "signal:" in body and "ocrLoadSeq" in body
    assert "ocrWorkspaceCurrent !== image) return" not in body, (
        "the same file at another page is a stale load too; compare the sequence"
    )
    assert body.count("seq !== ocrLoadSeq") >= 2


def test_the_rail_draws_thumbnails_not_full_pages():
    page_url = _code(_body(LIBRARY, "ocrPageImageUrl"))
    assert "thumb" in page_url and "?thumb=1" in page_url
    rail = _code(_body(LIBRARY, "ocrBuildPageRail"))
    assert "ocrPageImageUrl(image, index, true)" in rail


def test_a_file_seen_before_opens_with_its_page_count():
    sibling = _code(_body(LIBRARY, "ocrOpenSibling"))
    assert "ocrPageCounts.get(" in sibling


# --- O2: the picture and its place never wait for a reader ---------------------------


def test_the_picture_is_asked_for_before_the_regions():
    body = _code(_body(LIBRARY, "ocrLoadPage"))
    assert body.index("img.src = ocrPageImageUrl(") < body.index("ocrRegionsUrl(image")


def test_the_regions_request_is_not_awaited_before_the_page_is_set_up():
    body = _code(_body(LIBRARY, "ocrLoadPage"))
    ask = body.index("ocrRegionsUrl(image")
    assert "ocrApplyPageCount(" in body[:ask], "the rail is built from the cheap count, ahead of the reader"
    assert "ocrSyncPager(image, true)" in body[:ask]
    applied = _code(_body(LIBRARY, "ocrApplyPageCount"))
    assert "ocrBuildPageRail(" in applied and "ocrSyncPager(image, true)" in applied


# --- O3: overlays keep the nodes that did not change --------------------------------


def test_boxes_are_patched_in_place():
    render = _code(_body(LIBRARY, "ocrRenderRegions"))
    assert "boxes.replaceChildren()" not in render
    assert "ocrPaintBoxes(" in render
    paint = _code(_body(LIBRARY, "ocrPaintBoxes"))
    assert "replaceChildren" not in paint
    assert "ocrKeepNodes(" in paint


def test_live_words_are_patched_in_place():
    paint = _code(_body(LIBRARY, "ocrPaintLiveText"))
    assert "replaceChildren" not in paint
    assert "ocrKeepNodes(" in paint


def test_the_diff_removes_only_what_is_gone():
    keep = _code(_body(LIBRARY, "ocrKeepNodes"))
    assert "replaceChildren" not in keep and "innerHTML" not in keep
    assert ".remove()" in keep and "appendChild" in keep


def test_a_reload_of_the_same_page_leaves_the_overlays_alone():
    body = _code(_body(LIBRARY, "ocrLoadPage"))
    assert "samePage" in body
    clear = body.index("ocrPaintBoxes([])")
    assert "!samePage" in body[clear - 40 : clear], "the overlays go only when the page changed"
    assert 'ocr-boxes").replaceChildren' not in body
