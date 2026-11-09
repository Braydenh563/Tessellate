"""Tesseract runs once per page, not once per look at a page.

Reported (INBOX 314), verbatim: *"the tesseract generates it continuously not
only the first time or when prompted by the iser"*, on a scanned PDF opened in
the reading workspace.

The cause was measurable without a browser and without the binary: the
workspace fetches `GET .../ocr-regions?page=N` every time the current page
changes, and that route called `ocr.extract_regions` unconditionally. In scroll
mode an IntersectionObserver moves the current page as you scroll, so passing
over a six page scan ran the reader six times, and passing back over it ran it
six more. `core/ocr.py` says so itself: "every call re-reads the image".

Every test here counts calls into `ocr.extract_regions` against a fake that
returns a fixed answer. That is the whole measurement: the caching is what is
under test, not what Tesseract reads, and Tesseract is not installed here (see
CLAUDE.md section 4 on saying so rather than implying a reading was seen).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.core import ocr, pdfpages

from tests.test_ocr_pdf_regions import TWO_PAGE_PDF

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32

needs_pdfium = pytest.mark.skipif(
    not pdfpages.available(), reason="the pdfpages extra is not installed"
)


def _counting_reader(monkeypatch, calls: list[Path]):
    """`extract_regions` that records every call and answers like Tesseract."""

    def fake(path: Path):
        calls.append(Path(path))
        return {
            "width": 200,
            "height": 100,
            "regions": [
                {
                    "index": 0,
                    "kind": "text",
                    "text": "Hello world",
                    "confidence": 90.0,
                    "box": {"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.2},
                }
            ],
        }

    monkeypatch.setattr(ocr, "extract_regions", fake)
    return calls


def _attach(client, name: str, data: bytes) -> int:
    created = client.post("/entries", json={"content": "host note"}).json()
    upload = client.post(
        f"/entries/{created['id']}/files", files={"file": (name, data, "application/octet-stream")}
    )
    assert upload.status_code == 201, upload.text
    return upload.json()["attachments"][-1]["id"]


def test_an_image_is_read_once_however_often_its_regions_are_asked_for(client, monkeypatch):
    calls: list[Path] = []
    _counting_reader(monkeypatch, calls)
    attachment_id = _attach(client, "scan.png", PNG)

    for _ in range(4):
        body = client.get(f"/files/{attachment_id}/ocr-regions").json()
        assert body["source"] == "tesseract"
        assert [r["text"] for r in body["regions"]] == ["Hello world"]

    assert len(calls) == 1, f"the reader ran {len(calls)} times for four looks"


def test_asks_that_overlap_share_one_reading(client, monkeypatch):
    """INBOX 1716, "request 5753ms ... /files/4/ocr-regions": the viewer asks
    again before the first answer is stored, and each ask ran the reader."""
    import threading
    import time

    calls: list[Path] = []
    _counting_reader(monkeypatch, calls)
    inner = ocr.extract_regions

    def slow(path: Path):
        time.sleep(0.3)
        return inner(path)

    monkeypatch.setattr(ocr, "extract_regions", slow)
    attachment_id = _attach(client, "scan.png", PNG)
    bodies: list[dict] = []

    def ask():
        bodies.append(client.get(f"/files/{attachment_id}/ocr-regions").json())

    threads = [threading.Thread(target=ask) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(calls) == 1, f"the reader ran {len(calls)} times for four overlapping asks"
    assert [b["source"] for b in bodies] == ["tesseract"] * 4


def test_a_stored_reading_survives_a_new_request_intact(client, monkeypatch):
    """The second answer is the first answer, not a thinner one."""
    calls: list[Path] = []
    _counting_reader(monkeypatch, calls)
    attachment_id = _attach(client, "scan.png", PNG)
    first = client.get(f"/files/{attachment_id}/ocr-regions").json()
    second = client.get(f"/files/{attachment_id}/ocr-regions").json()
    assert first == second


@needs_pdfium
def test_scrolling_a_pdf_twice_reads_each_page_once(client, monkeypatch):
    """The reported case, as the workspace actually drives it.

    Two passes over every page is what scroll mode does the moment you scroll
    down and back up again.
    """
    calls: list[Path] = []
    _counting_reader(monkeypatch, calls)
    attachment_id = _attach(client, "lecture.pdf", TWO_PAGE_PDF)

    for _ in range(2):
        for page in (0, 1):
            body = client.get(f"/files/{attachment_id}/ocr-regions?page={page}").json()
            assert body["page"] == page
            assert body["source"] == "tesseract"

    assert len(calls) == 2, f"the reader ran {len(calls)} times for two passes over two pages"


@needs_pdfium
def test_re_reading_a_page_throws_its_stored_regions_away(client, monkeypatch, fake_ollama):
    """A cache that outlives the thing it caches is a lie about the page.

    Deleting the page's reading is the other half, and it takes the row with
    it, so it needs no separate invalidation.
    """
    calls: list[Path] = []
    _counting_reader(monkeypatch, calls)
    monkeypatch.setattr(ocr, "tesseract_available", lambda: True)
    #: Both halves of Tesseract (`ocr.engine_status`): the program and its package.
    monkeypatch.setattr(ocr, "packages_available", lambda: True)
    monkeypatch.setattr(ocr, "extract_text", lambda path: "Hello world")
    attachment_id = _attach(client, "lecture.pdf", TWO_PAGE_PDF)

    client.get(f"/files/{attachment_id}/ocr-regions?page=0")
    assert len(calls) == 1
    read = client.post(f"/files/{attachment_id}/ocr-page-read?page=0&reader=tesseract")
    assert read.status_code == 200, read.text
    client.get(f"/files/{attachment_id}/ocr-regions?page=0")
    assert len(calls) == 2, "a re-read must invalidate the regions it replaces"


@needs_pdfium
def test_a_stored_page_is_not_rasterised_again_to_answer_for_it(client, monkeypatch):
    """The render is the other per-look cost on this path, and it is serialised.

    `pdfpages` takes a process-wide lock around PDFium (its own docstring: a
    concurrent render corrupts the C heap), so a page rendered again for an
    answer already in hand queues behind every other page being scrolled past.
    """
    calls: list[Path] = []
    _counting_reader(monkeypatch, calls)
    renders: list[int] = []
    real_render = pdfpages.render_page
    monkeypatch.setattr(
        pdfpages,
        "render_page",
        lambda path, index, *a, **k: (renders.append(index), real_render(path, index, *a, **k))[1],
    )
    attachment_id = _attach(client, "lecture.pdf", TWO_PAGE_PDF)

    for _ in range(3):
        client.get(f"/files/{attachment_id}/ocr-regions?page=0")

    assert renders == [0], f"the page was rasterised {len(renders)} times for three looks"


@needs_pdfium
def test_a_page_whose_regions_are_stored_is_not_counted_as_read(client, monkeypatch):
    """Looking at a page is not the same claim as having read it.

    The stored regions are a cache of what the optical reader saw while the
    page was on screen; `PageRead.text` is a transcription somebody asked for.
    The Files row's "N pages read" badge and `_page_read_text_map` are built on
    the second, and a look must not inflate either.
    """
    calls: list[Path] = []
    _counting_reader(monkeypatch, calls)
    attachment_id = _attach(client, "lecture.pdf", TWO_PAGE_PDF)
    client.get(f"/files/{attachment_id}/ocr-regions?page=0")
    client.get(f"/files/{attachment_id}/ocr-regions?page=1")

    stored = client.get(f"/files/{attachment_id}/page-reads").json()
    assert stored["read"] == 0
    assert all(not (page["text"] or "").strip() for page in stored["pages"])
