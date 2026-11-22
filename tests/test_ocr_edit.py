"""A hand-corrected reading is what the OCR workspace shows (INBOX 443 (3)).

Found driving the editor: with Tesseract as the reader every look re-derived
the sections from the picture, so a saved correction never appeared. The
corrected text is stored as the page's sections until the next read.
"""

from __future__ import annotations

import base64
import threading

from tessellate.core import ocr

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _upload(client) -> int:
    response = client.post(
        "/media/upload",
        files={"file": ("page.png", _PNG, "image/png")},
        data={"direct": "true"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _engine_ready(monkeypatch):
    monkeypatch.setattr(ocr, "tesseract_available", lambda: True)
    monkeypatch.setattr(ocr, "packages_available", lambda: True)
    monkeypatch.setattr(ocr, "installed_languages", lambda: ["eng"])
    monkeypatch.setattr(ocr, "tesseract_version", lambda: "5.3.4")
    monkeypatch.setattr(
        ocr,
        "extract_regions",
        lambda path: {
            "width": 10,
            "height": 10,
            "source": "tesseract",
            "regions": [
                {
                    "index": 0,
                    "kind": "text",
                    "text": "machine words",
                    "confidence": 90.0,
                    "box": {"x": 0, "y": 0, "w": 1, "h": 1},
                }
            ],
        },
    )
    monkeypatch.setattr(ocr, "extract_text", lambda path: "machine words")


def test_a_hand_edit_is_shown_until_the_next_read(monkeypatch, client):
    media_id = _upload(client)
    _engine_ready(monkeypatch)
    first = client.get(f"/media/{media_id}/ocr-regions?auto=true").json()
    assert first["source"] == "tesseract"

    client.post(f"/media/{media_id}/ocr", json={"text": "Heading\n\nfixed by hand", "edited": True})
    again = client.get(f"/media/{media_id}/ocr-regions?auto=true").json()
    assert again["source"] == "edited-tesseract"
    assert "fixed by hand" in " ".join(r["text"] for r in again["regions"])
    assert [r["source"] for r in again["readings"] if r["in_regions"]] == ["tesseract"]

    # A fresh read replaces the edit.
    client.post(f"/media/{media_id}/ocr", json={})
    third = client.get(f"/media/{media_id}/ocr-regions?auto=true").json()
    assert third["source"] == "tesseract"


def test_tesseract_as_the_reader_is_not_told_to_switch_to_tesseract(monkeypatch, client):
    """Tesseract was the reader (`auto`) and placed nothing: the old message
    sent the person in a circle."""
    media_id = _upload(client)
    _engine_ready(monkeypatch)
    monkeypatch.setattr(ocr, "extract_regions", lambda path: None)
    client.post(f"/media/{media_id}/vision-ocr", json={"text": "read by a model"})
    body = client.get(f"/media/{media_id}/ocr-regions?auto=true").json()
    assert body["source"] == "reading"
    assert "Switch to Tesseract" not in body["message"]
    assert "could not mark" in body["message"]


def test_clearing_the_text_leaves_nothing_stale(monkeypatch, client):
    media_id = _upload(client)
    _engine_ready(monkeypatch)
    client.post(f"/media/{media_id}/ocr", json={"text": "kept"})
    client.post(f"/media/{media_id}/ocr", json={"text": ""})
    gone = client.get(f"/media/{media_id}/ocr-regions?auto=false").json()
    assert gone["source"] == "none"


def test_a_read_queued_before_a_clear_never_puts_the_text_back(monkeypatch, client):
    """The upload's own background read, held until after the person clears
    the text, stores nothing (CI py3.12 on 50462a6a: 'reading' == 'none')."""
    _engine_ready(monkeypatch)
    release, done = threading.Event(), threading.Event()
    reads = []

    def held_read(path):
        reads.append(path)
        release.wait(10)
        return "machine words"

    real_store = ocr.extract_and_store

    def store_then_signal(*args):
        try:
            real_store(*args)
        finally:
            done.set()

    monkeypatch.setattr(ocr, "extract_text", held_read)
    monkeypatch.setattr(ocr, "extract_and_store", store_then_signal)
    media_id = _upload(client)
    client.post(f"/media/{media_id}/ocr", json={"text": ""})
    release.set()
    assert done.wait(10), "the background read never ran"
    assert reads, "the upload queued no read"
    gone = client.get(f"/media/{media_id}/ocr-regions?auto=false").json()
    assert gone["source"] == "none"
