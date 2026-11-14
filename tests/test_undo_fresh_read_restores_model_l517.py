"""L517: Undo of a fresh read puts back the reading and who read it. A typed
vision reading may carry `model`; without it the stored name is left alone."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("app_state")

LIBRARY = Path(__file__).resolve().parents[1] / "frontend" / "js" / "library.js"


def _media(client) -> int:
    files = {"file": ("shot.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")}
    return client.post("/media/upload", files=files, data={"direct": "true"}).json()["id"]


def test_a_media_reading_written_with_a_model_names_that_model(client):
    mid = _media(client)
    client.post(f"/media/{mid}/vision-ocr", json={"text": "New read", "model": "big-vision:7b"})
    client.post(f"/media/{mid}/vision-ocr", json={"text": "Old read", "model": "small-vision:2b"})
    got = client.post(f"/media/{mid}/vision-ocr", json={"text": "Old read"}).json()
    assert got["vision_ocr_model"] == "small-vision:2b"


def test_an_attachment_reading_written_with_a_model_names_that_model(client):
    created = client.post("/entries", json={"content": "host note"}).json()
    files = {"file": ("scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")}
    aid = client.post(f"/entries/{created['id']}/files", files=files).json()["attachments"][-1]["id"]
    got = client.post(f"/files/{aid}/analyse", json={"kind": "vision", "text": "Old read", "model": "small-vision:2b"}).json()
    assert got["vision_ocr_model"] == "small-vision:2b"
    got = client.post(f"/files/{aid}/analyse", json={"kind": "vision", "text": "Edited"}).json()
    assert got["vision_ocr_model"] == "small-vision:2b"


def test_the_fresh_read_undo_carries_the_model_before_and_after():
    js = LIBRARY.read_text(encoding="utf-8")
    assert 'const beforeModel = image.vision_ocr_model || "";' in js
    assert "ocrTextWriter(image, kind, before, false, beforeModel)" in js
    assert 'if (kind === "vision-ocr" && model !== undefined) payload.model = model;' in js
