"""Page regions for the OCR workspace.

Asked for with three screenshots of Baidu's Unlimited-OCR: *"for the document
ocr I want smth like this"*, the page beside its regions, each region
separately readable, rather than one wall of text under the picture with no
way to tell which part of the page a line came from.

Tesseract is not installed in CI or in the sandbox this was written in, so
every test here drives `extract_regions` against a **fake** `pytesseract`
(the same fake-transport discipline the provider tests use). What that
proves is the grouping, the line breaks, the confidence filter and the
normalisation: not that Tesseract returns what this expects it to.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from tessellate.core import ocr

#: `extract_regions` reads the saved OCR language, which builds app state; without the
#: fixture that falls back to the repo's own `./data` (CI's serial PDF job caught it).
pytestmark = pytest.mark.usefixtures("app_state")


class _FakeImage:
    size = (200, 100)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _install_fake(monkeypatch, data):
    """A `pytesseract` and a `PIL.Image` that return exactly `data`."""
    fake_pt = types.ModuleType("pytesseract")
    fake_pt.Output = types.SimpleNamespace(DICT="dict")
    fake_pt.image_to_data = lambda img, output_type=None: data
    fake_pil = types.ModuleType("PIL")
    fake_image = types.ModuleType("PIL.Image")
    fake_image.open = lambda path: _FakeImage()
    fake_pil.Image = fake_image
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pt)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image)
    monkeypatch.setattr(ocr, "tesseract_available", lambda: True)


def _rows(words):
    """`image_to_data`'s dict-of-lists shape, one entry per word."""
    keys = ("text", "conf", "page_num", "block_num", "line_num", "left", "top", "width", "height")
    return {key: [word[i] for word in words] for i, key in enumerate(keys)}


def test_words_in_one_block_become_one_region(monkeypatch):
    _install_fake(
        monkeypatch,
        _rows([
            ("Hello", 96, 1, 1, 1, 10, 10, 40, 12),
            ("world", 95, 1, 1, 1, 55, 10, 40, 12),
        ]),
    )
    found = ocr.extract_regions(Path("x.png"))
    assert [r["text"] for r in found["regions"]] == ["Hello world"]


def test_a_new_line_in_the_same_block_becomes_a_newline(monkeypatch):
    """Joining every word with a space turned an address block into one
    run-on line."""
    _install_fake(
        monkeypatch,
        _rows([
            ("12", 90, 1, 1, 1, 10, 10, 20, 12),
            ("Main", 90, 1, 1, 1, 35, 10, 40, 12),
            ("Springfield", 90, 1, 1, 2, 10, 30, 90, 12),
        ]),
    )
    found = ocr.extract_regions(Path("x.png"))
    assert found["regions"][0]["text"] == "12 Main\nSpringfield"


def test_separate_blocks_stay_separate(monkeypatch):
    _install_fake(
        monkeypatch,
        _rows([
            ("Top", 90, 1, 1, 1, 10, 10, 30, 12),
            ("Bottom", 90, 1, 2, 1, 10, 70, 50, 12),
        ]),
    )
    found = ocr.extract_regions(Path("x.png"))
    assert [r["text"] for r in found["regions"]] == ["Top", "Bottom"]
    assert [r["index"] for r in found["regions"]] == [0, 1]


def test_the_box_is_a_fraction_of_the_image(monkeypatch):
    """Pixels would make every overlay wrong at every size but one, the
    image is drawn scaled to whatever width the panel happens to be."""
    _install_fake(monkeypatch, _rows([("Word", 90, 1, 1, 1, 20, 25, 40, 25)]))
    box = ocr.extract_regions(Path("x.png"))["regions"][0]["box"]
    # The fake image is 200x100.
    assert box == {"x": 0.1, "y": 0.25, "w": 0.2, "h": 0.25}


def test_low_confidence_words_are_dropped(monkeypatch):
    """Tesseract invents punctuation noise at the edges of a photograph, and
    reports -1 for its own structural rows."""
    _install_fake(
        monkeypatch,
        _rows([
            ("Real", 88, 1, 1, 1, 10, 10, 30, 12),
            ("~", 4, 1, 1, 1, 45, 10, 6, 12),
            ("", -1, 1, 1, 1, 0, 0, 200, 100),
        ]),
    )
    found = ocr.extract_regions(Path("x.png"))
    assert [r["text"] for r in found["regions"]] == ["Real"]


def test_a_much_taller_block_is_called_a_heading(monkeypatch):
    _install_fake(
        monkeypatch,
        _rows([
            ("TITLE", 90, 1, 1, 1, 10, 5, 80, 30),
            ("body", 90, 1, 2, 1, 10, 50, 40, 12),
            ("text", 90, 1, 2, 1, 55, 50, 40, 12),
        ]),
    )
    kinds = {r["text"]: r["kind"] for r in ocr.extract_regions(Path("x.png"))["regions"]}
    assert kinds["TITLE"] == "heading"
    assert kinds["body text"] == "text"


def test_no_tesseract_is_none_not_empty(monkeypatch):
    """`None` and `[]` are different answers: "nothing is installed" and
    "this page has no text on it". The workspace says which."""
    monkeypatch.setattr(ocr, "tesseract_available", lambda: False)
    assert ocr.extract_regions(Path("x.png")) is None


def test_an_unreadable_image_never_raises(monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("corrupt")

    fake_pt = types.ModuleType("pytesseract")
    fake_pt.Output = types.SimpleNamespace(DICT="dict")
    fake_pt.image_to_data = boom
    fake_pil = types.ModuleType("PIL")
    fake_image = types.ModuleType("PIL.Image")
    fake_image.open = lambda path: _FakeImage()
    fake_pil.Image = fake_image
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pt)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image)
    monkeypatch.setattr(ocr, "tesseract_available", lambda: True)
    assert ocr.extract_regions(Path("x.png")) is None


def test_the_route_refuses_a_file_with_no_pages_and_no_pixels(client):
    """A .txt has neither an image Tesseract can read nor a page that can be
    rasterised, so 415 stands for it.

    A **PDF no longer refuses**, see `test_ocr_pdf_regions.py`. That 415 was
    the whole of "is the document ocr even working??": the rasterisation step
    this test's older docstring said the feature "does not pull in" had in fact
    existed since `core/pdfpages.py` was written for the file viewer, and only
    the join was missing."""
    files = {"file": ("notes.txt", b"hello", "application/octet-stream")}
    created = client.post("/entries", json={"content": "host note"}).json()
    upload = client.post(f"/entries/{created['id']}/files", files=files)
    assert upload.status_code == 201, upload.text
    attachment_id = upload.json()["attachments"][-1]["id"]
    assert client.get(f"/files/{attachment_id}/ocr-regions").status_code == 415


def test_a_pdf_is_read_page_by_page_rather_than_refused(client):
    """The document case, at the route rather than the helper: a PDF answers
    200 with a page count, whatever is or is not installed to read it."""
    created = client.post("/entries", json={"content": "host note"}).json()
    files = {"file": ("scan.pdf", b"%PDF-1.4\ntrailer<</Root 1 0 R>>", "application/pdf")}
    upload = client.post(f"/entries/{created['id']}/files", files=files)
    attachment_id = upload.json()["attachments"][-1]["id"]
    response = client.get(f"/files/{attachment_id}/ocr-regions")
    assert response.status_code == 200, response.text
    assert "pages" in response.json()


def test_without_tesseract_the_sections_come_from_the_reading(client, monkeypatch):
    """Tesseract missing is the *common* case (it is a system binary, not a
    wheel), and this app's primary reader is a vision model anyway.

    This used to answer with one region covering the whole page, badged
    "stored-text", honest, and useless: it threw away the structure the
    reading already had because it could not draw a rectangle around it.
    Reported as "the regions dont work without tesseract but surely there's a
    better way". Now the reading is split into its own blocks, typed by shape,
    and `box` is **None** rather than a full-page rectangle, a box that
    claims to be the whole page is a wrong answer, not a missing one.
    """
    monkeypatch.setattr(ocr, "extract_regions", lambda path: None)
    created = client.post("/entries", json={"content": "host note"}).json()
    files = {"file": ("scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")}
    upload = client.post(f"/entries/{created['id']}/files", files=files)
    attachment_id = upload.json()["attachments"][-1]["id"]
    reading = "Invoice\n\nAmount due is forty pounds.\n\n- one\n- two\n- three"
    client.post(f"/files/{attachment_id}/analyse", json={"kind": "ocr", "text": reading})

    body = client.get(f"/files/{attachment_id}/ocr-regions").json()
    assert body["source"] == "reading"
    assert [r["kind"] for r in body["regions"]] == ["heading", "text", "list"]
    assert body["regions"][0]["text"] == "Invoice"
    # Nothing measured where these are, so nothing claims to have.
    assert all(r["box"] is None for r in body["regions"])
    # Tesseract is genuinely missing here (not mocked), so the message
    # tells you to install it, the honest instruction for this case.
    assert "Install Tesseract" in body["message"]


def test_with_tesseract_already_installed_the_message_says_switch_not_install(client, monkeypatch):
    """INBOX 423(d): the vision model is the default reader, so a reading
    with no page positions is the common case even on a machine that already
    has Tesseract, simply not chosen. "Install Tesseract" is then wrong
    advice, wrong enough to act on: the message must say to switch reader
    instead, worded by `ocr.tesseract_available()`, the same check the
    "nothing read yet" message next to this one already makes."""
    monkeypatch.setattr(ocr, "extract_regions", lambda path: None)
    monkeypatch.setattr(ocr, "tesseract_available", lambda: True)
    # Both halves (op4-1005): "switch to" is offered only for a reader that
    # can read, which the program alone without its wrapper cannot.
    monkeypatch.setattr(ocr, "packages_available", lambda: True)
    created = client.post("/entries", json={"content": "host note"}).json()
    files = {"file": ("scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")}
    upload = client.post(f"/entries/{created['id']}/files", files=files)
    attachment_id = upload.json()["attachments"][-1]["id"]
    client.post(
        f"/files/{attachment_id}/analyse",
        json={"kind": "vision", "text": "A page read by the vision model."},
    )

    body = client.get(f"/files/{attachment_id}/ocr-regions?auto=false").json()
    assert body["source"] == "reading"
    assert "Switch to Tesseract" in body["message"]
    assert "Install" not in body["message"]


# --- the workspace shows what the lightbox shows (INBOX 421 e) ---------------
#
# The owner: "the text in the lightbox doesnt even appear in the ocr
# workspace". The lightbox reads both stored fields (`lightboxReadingsFor`);
# the workspace, with its reader set to the vision model (auto=0, the owner's
# setting: no Tesseract), answered an empty page whatever was stored.


def _attached_png(client):
    created = client.post("/entries", json={"content": "host note"}).json()
    files = {"file": ("scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")}
    upload = client.post(f"/entries/{created['id']}/files", files=files)
    return upload.json()["attachments"][-1]["id"]


def test_with_the_vision_reader_chosen_a_stored_reading_still_shows(client, monkeypatch):
    called = []
    monkeypatch.setattr(ocr, "extract_regions", lambda path: called.append(path) or None)
    attachment_id = _attached_png(client)
    client.post(f"/files/{attachment_id}/analyse", json={"kind": "vision", "text": "Goal\n\nPeople and tests."})

    body = client.get(f"/files/{attachment_id}/ocr-regions?page=0&auto=0").json()
    assert body["source"] == "reading"
    assert "".join(r["text"] for r in body["regions"]).startswith("Goal")
    # Still no Tesseract run nobody asked for.
    assert called == []


def test_both_stored_readings_come_back_labelled_by_source(client, monkeypatch):
    monkeypatch.setattr(ocr, "extract_regions", lambda path: None)
    attachment_id = _attached_png(client)
    client.post(f"/files/{attachment_id}/analyse", json={"kind": "vision", "text": "Read by the model"})
    client.post(f"/files/{attachment_id}/analyse", json={"kind": "ocr", "text": "Read by Tesseract"})

    body = client.get(f"/files/{attachment_id}/ocr-regions?page=0&auto=0").json()
    readings = {r["source"]: r for r in body["readings"]}
    assert readings["vision"]["text"] == "Read by the model"
    assert readings["tesseract"]["text"] == "Read by Tesseract"
    assert "Tesseract" in readings["tesseract"]["label"]
    # The sections above are the vision reading's, the same one the lightbox
    # puts first; the other is the one listed beside them.
    assert readings["vision"]["in_regions"] is True
    assert readings["tesseract"]["in_regions"] is False


def test_a_media_upload_lists_its_readings_too(client, monkeypatch):
    monkeypatch.setattr(ocr, "extract_regions", lambda path: None)
    files = {"file": ("shot.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")}
    upload = client.post("/media/upload", files=files, data={"direct": "true"}).json()
    client.post(f"/media/{upload['id']}/vision-ocr", json={"text": "Seen by a model"})

    body = client.get(f"/media/{upload['id']}/ocr-regions?page=0&auto=0").json()
    assert [(r["source"], r["in_regions"]) for r in body["readings"]] == [("vision", True)]
    assert body["regions"]


def test_each_word_keeps_its_own_box_for_live_text(monkeypatch):
    """Live Text (WORLD_CLASS_PLAN 28.4 row 7): a region carries its words,
    each where it sits on the page, in reading order, so the workspace can lay
    selectable text over the picture."""
    _install_fake(
        monkeypatch,
        _rows([
            ("Hello", 96, 1, 1, 1, 10, 10, 40, 12),
            ("world", 95, 1, 1, 1, 55, 10, 40, 12),
        ]),
    )
    region = ocr.extract_regions(Path("x.png"))["regions"][0]
    assert [w["text"] for w in region["words"]] == ["Hello", "world"]
    first, second = region["words"]
    assert first["x"] < second["x"]
    assert 0 < first["w"] < 1 and 0 < first["h"] < 1


def test_rapidocr_lines_are_cut_into_words_in_order():
    words = ocr._line_words("Read chapter 7", 0, 0, 140, 10, 200, 100)
    assert [w["text"] for w in words] == ["Read", "chapter", "7"]
    assert words[0]["x"] < words[1]["x"] < words[2]["x"]
    assert abs(words[-1]["x"] + words[-1]["w"] - 0.7) < 0.01
