"""OCR workspace page reads: ranges, single pages, background tasks and persisted readings."""

from __future__ import annotations

import io

import pytest

from tessellate.ai import vision_ocr
from tessellate.api import routes_files, routes_tasks
from tessellate.api import routes_files_ocr as files_service  # the OCR read moved there (K24)
from tessellate.api.routes_files_readings import MAX_RANGE_PAGES, _parse_page_spec  # moved with their routes (K24)
from tessellate.core import pdfpages


# Reading a PDF by page range: the range parser (the read itself loops over the single-page reader).


@pytest.mark.parametrize(
    ("spec", "count", "expected"),
    [
        # "everything", in the two spellings a caller might send.
        ("all", 5, [0, 1, 2, 3, 4]),
        ("*", 3, [0, 1, 2]),
        # Empty means the same as "all": the control defaults to the whole
        # document, so a blank box must not read nothing.
        ("", 3, [0, 1, 2]),
        # One-based on the way in, because that is what the page rail shows.
        ("1", 5, [0]),
        ("2-2", 5, [1]),
        ("1-3", 5, [0, 1, 2]),
        ("1,4", 5, [0, 3]),
        ("1-2,4-5", 5, [0, 1, 3, 4]),
        (" 1 - 2 , 4 ", 5, [0, 1, 3]),  # spaces are how people actually type
    ],
)
def test_a_page_spec_becomes_the_pages_a_person_meant(spec, count, expected):
    assert _parse_page_spec(spec, count) == expected


def test_a_backwards_range_is_read_the_way_it_was_meant():
    """"3-1" is a typo for "1-3", not an empty selection."""
    assert _parse_page_spec("3-1", 5) == [0, 1, 2]


def test_a_range_past_the_end_is_clamped_to_the_document():
    assert _parse_page_spec("1-99", 3) == [0, 1, 2]


def test_page_zero_does_not_exist_because_people_count_from_one():
    assert _parse_page_spec("0", 3) == []


def test_junk_is_skipped_rather_than_refusing_the_whole_range():
    """A stray character should cost you that one part, not the request.

    Refusing everything would mean a mistyped range reads nothing and says
    little; this reads the pages it could understand.
    """
    assert _parse_page_spec("abc", 3) == []
    assert _parse_page_spec("1,abc,3", 5) == [0, 2]


def test_duplicates_and_overlaps_collapse():
    """Asking for a page twice must not read it twice, a vision pass is
    seconds per page, and the overlap in "1-3,2-4" is easy to type."""
    assert _parse_page_spec("1-3,2-4", 10) == [0, 1, 2, 3]
    assert _parse_page_spec("2,2,2", 5) == [1]


def test_there_is_a_ceiling_on_one_request():
    """"All" on a 300-page scan is not a request anyone means synchronously."""
    assert MAX_RANGE_PAGES > 0
    assert len(_parse_page_spec("all", 300)) == 300  # the parser is honest…
    # …and the cap is applied by `_vision_read_range`, which reports how far it
    # got so the reader can ask for the next block.


# Reading one page with the vision model: the refusals and the routing; nothing is stored.


ONE_PAGE_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]/Contents 4 0 R"
    b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 44>>stream\nBT /F1 24 Tf 20 40 Td (Hello OCR) Tj ET\n"
    b"endstream endobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"trailer<</Root 1 0 R>>"
)


def _attach(client, name: str, data: bytes) -> int:
    created = client.post("/entries", json={"content": "host note"}).json()
    upload = client.post(
        f"/entries/{created['id']}/files",
        files={"file": (name, io.BytesIO(data), "application/octet-stream")},
    )
    assert upload.status_code == 201, upload.text
    return upload.json()["attachments"][-1]["id"]


def test_only_a_pdf_is_read_a_page_at_a_time(client):
    """An image *is* one page, it goes through the ordinary vision read, and
    offering a page-scoped route for it would imply a page rail that does not
    exist."""
    attachment_id = _attach(client, "photo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    response = client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    assert response.status_code == 415


def test_a_missing_model_is_a_409_not_a_500(client):
    """The commonest state on this machine: no Ollama running. The workspace
    shows the message; a 500 would show a stack trace to somebody whose only
    problem is that they have not started their model server."""
    if not pdfpages.available():
        pytest.skip("the pdfpages extra is not installed")
    attachment_id = _attach(client, "scan.pdf", ONE_PAGE_PDF)
    response = client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    assert response.status_code == 409
    assert "model" in response.json()["detail"].lower()


def test_without_the_rasteriser_it_answers_rather_than_failing(client, monkeypatch):
    """No pypdfium2 means no pixels to read, which is a *state* rather than an
    error: the reader is told what to install, in the response body, at 200."""
    monkeypatch.setattr(pdfpages, "available", lambda: False)
    attachment_id = _attach(client, "scan.pdf", ONE_PAGE_PDF)
    response = client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    assert response.status_code == 200
    assert "rasteriser" in response.json()["message"]
    assert response.json()["text"] == ""


def test_an_unknown_attachment_is_a_404(client):
    assert client.post("/files/9999/ocr-page-read?page=0").status_code == 404


# A PDF page read shows up in Settings, Background tasks, while it runs.


def test_a_running_page_read_is_listed_as_a_background_task():
    token = vision_ocr.register_page_read("Reading page 4 of scan.pdf")
    try:
        kinds = {task["kind"]: task for task in routes_tasks.collect()}
        assert "page-read" in kinds, "a running page read must appear in GET /tasks"
        assert kinds["page-read"]["label"] == "Reading page 4 of scan.pdf"
    finally:
        vision_ocr.finish_page_read(token)


def test_a_finished_page_read_leaves_the_list():
    token = vision_ocr.register_page_read("Reading page 1 of scan.pdf")
    vision_ocr.finish_page_read(token)
    assert all(task["kind"] != "page-read" for task in routes_tasks.collect())


def test_finishing_twice_is_not_an_error():
    # `_read_page` drops it in a `finally`, and a `finally` that can throw
    # hides the real error.
    token = vision_ocr.register_page_read("Reading page 2 of scan.pdf")
    vision_ocr.finish_page_read(token)
    vision_ocr.finish_page_read(token)


def test_the_reader_is_named_when_it_is_tesseract():
    token = vision_ocr.register_page_read("Reading page 3", model="Tesseract")
    try:
        task = next(t for t in routes_tasks.collect() if t["kind"] == "page-read")
        assert "Tesseract" in task["detail"]
    finally:
        vision_ocr.finish_page_read(token)


# A page reading survives the workspace being closed (PageRead rows and GET page-reads).


def test_a_document_with_nothing_read_reports_nothing(client):
    attachment_id = _attach(client, "blank.pdf", ONE_PAGE_PDF)
    body = client.get(f"/files/{attachment_id}/page-reads").json()
    assert body["pages"] == []
    assert body["read"] == 0


def test_a_reading_is_stored_and_handed_back(client, monkeypatch):
    """The report, end to end: read a page, then ask as if the window reopened."""
    attachment_id = _attach(client, "scan.pdf", ONE_PAGE_PDF)
    if not pdfpages.available():
        pytest.skip("the PDF rasteriser extra is not installed here")

    monkeypatch.setattr(
        files_service,
        "_vision_read_page",
        lambda path, index, reader="vision": routes_files.OcrPageReadOut(
            page=index, text="The words on the page.", model="stub-vision"
        ),
    )
    read = client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    assert read.status_code == 200, read.text
    assert read.json()["text"] == "The words on the page."

    # Now the part that was broken: come back to it later.
    later = client.get(f"/files/{attachment_id}/page-reads").json()
    assert [page["page"] for page in later["pages"]] == [0]
    assert later["pages"][0]["text"] == "The words on the page."
    assert later["pages"][0]["model"] == "stub-vision"
    assert later["read"] == 1


def test_re_reading_a_page_replaces_it_rather_than_stacking(client, monkeypatch):
    attachment_id = _attach(client, "scan.pdf", ONE_PAGE_PDF)
    if not pdfpages.available():
        pytest.skip("the PDF rasteriser extra is not installed here")

    texts = iter(["first attempt", "second, better attempt"])
    monkeypatch.setattr(
        files_service,
        "_vision_read_page",
        lambda path, index, reader="vision": routes_files.OcrPageReadOut(
            page=index, text=next(texts), model="stub-vision"
        ),
    )
    client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    pages = client.get(f"/files/{attachment_id}/page-reads").json()["pages"]
    assert len(pages) == 1, "one page must have one reading, not a history of them"
    assert pages[0]["text"] == "second, better attempt"


def test_an_empty_reading_is_not_stored(client, monkeypatch):
    """"Nothing found on page 4" is not a transcription.

    Storing it would make a later, better reader look like it had nothing to
    add: the pane would show a stored blank instead of asking again.
    """
    attachment_id = _attach(client, "scan.pdf", ONE_PAGE_PDF)
    if not pdfpages.available():
        pytest.skip("the PDF rasteriser extra is not installed here")

    monkeypatch.setattr(
        files_service,
        "_vision_read_page",
        lambda path, index, reader="vision": routes_files.OcrPageReadOut(
            page=index, text="", message="nothing found"
        ),
    )
    client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    assert client.get(f"/files/{attachment_id}/page-reads").json()["pages"] == []


def test_a_range_read_stores_every_page_it_managed(client, monkeypatch):
    attachment_id = _attach(client, "scan.pdf", ONE_PAGE_PDF)
    if not pdfpages.available():
        pytest.skip("the PDF rasteriser extra is not installed here")

    monkeypatch.setattr(
        files_service,
        "_vision_read_page",
        lambda path, index, reader="vision": routes_files.OcrPageReadOut(
            page=index, text=f"page {index + 1}", model="stub-vision"
        ),
    )
    body = client.post(f"/files/{attachment_id}/ocr-range-read?pages=all").json()
    assert body["read"] >= 1
    stored = client.get(f"/files/{attachment_id}/page-reads").json()
    assert [page["text"] for page in stored["pages"]] == ["page 1"]


# --- delete -------------------------------------------------------------
#
# Reported directly: "there's also no way to delete or redo ocr text
# extractions in the ocr workspace." Redo already worked (the test just above
# this one pins it, a re-read replaces the row); delete genuinely did not,
# and these are its coverage.


def test_deleting_a_page_read_removes_it(client, monkeypatch):
    attachment_id = _attach(client, "scan.pdf", ONE_PAGE_PDF)
    if not pdfpages.available():
        pytest.skip("the PDF rasteriser extra is not installed here")

    monkeypatch.setattr(
        files_service,
        "_vision_read_page",
        lambda path, index, reader="vision": routes_files.OcrPageReadOut(
            page=index, text="a reading worth deleting", model="stub-vision"
        ),
    )
    client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    assert client.get(f"/files/{attachment_id}/page-reads").json()["read"] == 1

    deleted = client.delete(f"/files/{attachment_id}/page-reads/0")
    assert deleted.status_code == 200, deleted.text
    # The delete route hands back what is left, so the workspace can repaint
    # without a second request.
    assert deleted.json()["pages"] == []

    after = client.get(f"/files/{attachment_id}/page-reads").json()
    assert after["pages"] == []
    assert after["read"] == 0


def test_deleting_a_page_that_was_never_read_is_not_an_error(client):
    """Idempotent, matching the rest of this table's own stance that it is a
    cache of a reading rather than the reading itself, deleting a row that
    was never there is the state the caller wanted, not a failure."""
    attachment_id = _attach(client, "blank.pdf", ONE_PAGE_PDF)
    response = client.delete(f"/files/{attachment_id}/page-reads/0")
    assert response.status_code == 200, response.text
    assert response.json()["pages"] == []


def test_deleting_one_page_leaves_the_others(client, monkeypatch):
    """A delete is scoped to the page you are looking at, not the whole
    document: the OCR workspace reads and deletes one page at a time, and a
    delete that took the rest with it would silently undo work on pages the
    person never touched."""
    attachment_id = _attach(client, "scan.pdf", ONE_PAGE_PDF)
    if not pdfpages.available():
        pytest.skip("the PDF rasteriser extra is not installed here")

    monkeypatch.setattr(
        files_service,
        "_vision_read_page",
        lambda path, index, reader="vision": routes_files.OcrPageReadOut(
            page=index, text=f"page {index + 1}", model="stub-vision"
        ),
    )
    client.post(f"/files/{attachment_id}/ocr-page-read?page=0")
    # Fake a second page's reading directly, since this fixture PDF has only
    # one real page: the identity this test cares about is the (kind,
    # source_id, page) key, not whether the document actually has two pages.
    from tessellate.core import deps
    from tessellate.core.database import PageRead

    with deps.get_db().session() as session:
        session.add(PageRead(kind="attachment", source_id=attachment_id, page=1, text="page 2"))
        session.commit()

    client.delete(f"/files/{attachment_id}/page-reads/0")
    remaining = client.get(f"/files/{attachment_id}/page-reads").json()["pages"]
    assert [p["page"] for p in remaining] == [1]


def test_media_page_reads_can_be_deleted_too(client, monkeypatch):
    """The upload-table sibling of the attachment route above, two id
    spaces, two routes, one shared implementation underneath."""
    upload = client.post(
        "/media/upload",
        files={"file": ("scan.pdf", io.BytesIO(ONE_PAGE_PDF), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    upload_id = upload.json()["id"]
    if not pdfpages.available():
        pytest.skip("the PDF rasteriser extra is not installed here")

    monkeypatch.setattr(
        files_service,
        "_vision_read_page",
        lambda path, index, reader="vision": routes_files.OcrPageReadOut(
            page=index, text="read from an upload", model="stub-vision"
        ),
    )
    client.post(f"/media/{upload_id}/ocr-page-read?page=0")
    assert client.get(f"/media/{upload_id}/page-reads").json()["read"] == 1

    deleted = client.delete(f"/media/{upload_id}/page-reads/0")
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"/media/{upload_id}/page-reads").json()["pages"] == []


def test_a_range_read_is_an_activity_job_with_progress_and_stop(monkeypatch, tmp_path):
    """L-world-class-67 (decision 70): a range read lists in the Activity panel, reports pages done, and Stop ends
    it between two pages, keeping the pages read so far."""
    from tessellate.api import routes_files_readings as readings
    from tessellate.core import activity

    monkeypatch.setattr(readings.pdfpages, "available", lambda: True)
    monkeypatch.setattr(readings.pdfpages, "page_count", lambda path: 6)
    seen: list[dict] = []

    def fake_read(path, index, reader, key):
        row = next(row for row in activity.snapshot() if row["kind"] == "ocr-range")
        seen.append(row)
        if index == 2:
            activity.stop(row["id"])
        return routes_files.OcrPageReadOut(page=index, text=f"page {index + 1}")

    monkeypatch.setattr(readings.rf, "_read_page", fake_read)
    out = readings._read_range(tmp_path / "x.pdf", "all", "vision", None)
    assert [p.text for p in out.pages] == ["page 1", "page 2", "page 3"]
    assert "Stopped" in out.message
    assert seen[0]["stoppable"] is True and not seen[0]["progress"]
    assert seen[2]["progress"] == pytest.approx(2 / 6)
    assert not [row for row in activity.snapshot() if row["kind"] == "ocr-range"]
